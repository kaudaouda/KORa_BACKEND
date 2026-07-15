from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, renderer_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import json
import time
import hashlib
import logging
from datetime import timedelta
from django.http import StreamingHttpResponse
from django.db.models import Max, Subquery, OuterRef

from ..media_paths import validate_uploaded_file
from ..models import (
    Nature, Categorie, Source, ActionType, Statut,
    EtatMiseEnOeuvre, Appreciation, Media, Direction,
    SousDirection, Service, Processus, Preuve, ActivityLog, StatutActionCDR,
    NotificationSettings, DashboardNotificationSettings, EmailSettings, DysfonctionnementRecommandation, Frequence,
    FrequenceRisque, GraviteRisque, CriticiteRisque, Risque, Mois, TypeDocument,
    Role, UserProcessus, UserProcessusRole, Notification, NotificationPolicy,
    ReminderEmailLog, FailedLoginAttempt, LoginSecurityConfig, LoginBlock,
)
from ..utils.notification_policy import should_notify_pac
from ..serializers import (
    AppreciationSerializer, CategorieSerializer, DirectionSerializer,
    SousDirectionSerializer, ActionTypeSerializer, NotificationSettingsSerializer,
    DashboardNotificationSettingsSerializer, EmailSettingsSerializer, FrequenceSerializer,
    RisqueSerializer, StatutActionCDRSerializer,
    RoleSerializer, UserProcessusSerializer, UserProcessusRoleSerializer,
    UserSerializer, UserCreateSerializer, UserInviteSerializer,
    CriticiteRisqueSerializer, DysfonctionnementRecommandationSerializer,
    NatureSerializer, ProcessusSerializer, ServiceSerializer,
    MoisSerializer, FrequenceRisqueSerializer, GraviteRisqueSerializer,
    TypeDocumentSerializer,
)
from ..utils.email_security import EmailValidator, EmailContentSanitizer, EmailRateLimiter, SecureEmailLogger
from ..utils.email_config import load_email_settings_into_django
from permissions.permissions import (
    DashboardPreuveUpdatePermission,
    DashboardMediaUpdatePermission,
    DashboardMediaCreatePermission,
)

logger = logging.getLogger(__name__)

from .utils import (
    ServerSentEventRenderer, get_client_ip, _parse_user_agent,
    log_activity, get_model_list_data,
)



def _read_cron_fields(trigger):
    """Extrait (hour, minute) depuis un CronTrigger APScheduler."""
    from apscheduler.triggers.cron import CronTrigger
    if not isinstance(trigger, CronTrigger):
        return None, None
    hour = minute = None
    for field in trigger.fields:
        field_str = str(field)
        if field.name == 'hour' and field_str != '*':
            try:
                hour = int(field_str)
            except ValueError:
                if '=' in field_str:
                    try:
                        hour = int(field_str.split('=')[1].strip("'"))
                    except (ValueError, IndexError):
                        pass
        elif field.name == 'minute' and field_str != '*':
            try:
                minute = int(field_str)
            except ValueError:
                if '=' in field_str:
                    try:
                        minute = int(field_str.split('=')[1].strip("'"))
                    except (ValueError, IndexError):
                        pass
    return hour, minute


def _extract_job_info(job):
    """
    Extrait (hour, minute, name) depuis un DjangoJob.

    Priorité 1 : scheduler live en mémoire (disponible uniquement dans le process
                 du service kora-scheduler, pas dans les workers Gunicorn).
    Priorité 2 : pickle job_state stocké dans la DB — toujours disponible.
    """
    import pickle
    from apscheduler.triggers.cron import CronTrigger
    from parametre.scheduler import scheduler as _scheduler

    name = hour = minute = None

    # Priorité 1 : scheduler live
    try:
        if _scheduler and _scheduler.running:
            live_job = _scheduler.get_job(job.id)
            if live_job:
                name = live_job.name
                hour, minute = _read_cron_fields(live_job.trigger)
                return hour, minute, name
    except Exception:
        pass

    # Priorité 2 : pickle en DB
    if job.job_state:
        try:
            job_state = (
                pickle.loads(job.job_state)
                if isinstance(job.job_state, bytes)
                else job.job_state
            )
            if isinstance(job_state, dict):
                name = job_state.get('name') or job.id
                hour, minute = _read_cron_fields(job_state.get('trigger'))
        except Exception:
            pass

    return hour, minute, name


def _serialize_job(job):
    from django_apscheduler.models import DjangoJobExecution
    hour, minute, name = _extract_job_info(job)
    last_exec = (
        DjangoJobExecution.objects
        .filter(job=job)
        .order_by('-run_time')
        .values('run_time', 'status', 'exception', 'duration')
        .first()
    )
    return {
        'id':            job.id,
        'name':          name or job.id,
        'next_run_time': job.next_run_time,
        'hour':          hour,
        'minute':        minute,
        'last_execution': last_exec,
    }


def _can_access_scheduler_admin(user):
    """Seul le superadmin Django (is_staff + is_superuser) peut gérer le scheduler."""
    from parametre.permissions import can_manage_users
    return can_manage_users(user)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_scheduler_jobs(request):
    """Liste des jobs du scheduler avec trigger info et dernière exécution."""
    if not _can_access_scheduler_admin(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from django_apscheduler.models import DjangoJob
    from parametre.scheduler import scheduler as _scheduler

    jobs = DjangoJob.objects.all().order_by('id')
    scheduler_running = bool(_scheduler and _scheduler.running)
    return Response({
        'scheduler_running': scheduler_running,
        'jobs': [_serialize_job(j) for j in jobs],
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def admin_scheduler_job_update(request, job_id):
    """
    Modifie l'heure/minute cron d'un job.

    Architecture : le scheduler tourne dans un service systemd séparé. Ce worker
    Gunicorn ne peut pas appeler reschedule_job() directement. Il :
      1. Met à jour le pickle du DjangoJob en DB (rend le GET immédiatement cohérent).
      2. Dépose un fichier de commande JSON dans /tmp.
    Le service scheduler lit ce fichier dans les 30 secondes et applique le changement.
    """
    import pickle
    from apscheduler.triggers.cron import CronTrigger
    from django_apscheduler.models import DjangoJob
    from parametre.scheduler import write_scheduler_command

    if not _can_access_scheduler_admin(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        job = DjangoJob.objects.get(id=job_id)
    except DjangoJob.DoesNotExist:
        return Response({'error': 'Job introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    errors = {}
    try:
        hour = int(request.data.get('hour', -1))
        if not (0 <= hour <= 23):
            raise ValueError
    except (TypeError, ValueError):
        errors['hour'] = 'Heure invalide (0-23).'
    try:
        minute = int(request.data.get('minute', -1))
        if not (0 <= minute <= 59):
            raise ValueError
    except (TypeError, ValueError):
        errors['minute'] = 'Minute invalide (0-59).'
    if errors:
        return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    new_trigger = CronTrigger(hour=hour, minute=minute)

    # 1. Mettre à jour le pickle en DB pour cohérence immédiate du GET.
    if job.job_state:
        try:
            job_state = (
                pickle.loads(job.job_state)
                if isinstance(job.job_state, bytes)
                else job.job_state
            )
            if isinstance(job_state, dict):
                job_state['trigger'] = new_trigger
                job.job_state = pickle.dumps(job_state)
                job.save(update_fields=['job_state'])
        except Exception as e:
            logger.warning("[SCHEDULER] Mise à jour pickle DB échouée pour %s: %s", job_id, e)

    # 2. Signaler au service scheduler de reschedule_job dans les 30 s.
    try:
        write_scheduler_command('reschedule', job_id, hour=hour, minute=minute)
        logger.info("[SCHEDULER] Commande reschedule envoyée: %s → %02dh%02d", job_id, hour, minute)
    except Exception as e:
        logger.error("[SCHEDULER] Impossible d'envoyer la commande reschedule: %s", e)
        return Response(
            {'error': 'Impossible de contacter le service scheduler.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    job.refresh_from_db()
    return Response(_serialize_job(job))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_scheduler_job_trigger(request, job_id):
    """
    Déclenche manuellement un job.
    Dépose une commande 'trigger' lue par le service scheduler dans les 30 s.
    """
    from django_apscheduler.models import DjangoJob
    from parametre.scheduler import write_scheduler_command

    if not _can_access_scheduler_admin(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    if not DjangoJob.objects.filter(id=job_id).exists():
        return Response({'error': 'Job introuvable.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        write_scheduler_command('trigger', job_id)
        logger.info("[SCHEDULER] Commande trigger envoyée pour %s par %s", job_id, request.user.username)
    except Exception as e:
        logger.error("[SCHEDULER] Impossible d'envoyer la commande trigger: %s", e)
        return Response(
            {'error': 'Impossible de contacter le service scheduler.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({'message': f'Job « {job_id} » sera déclenché dans moins de 30 secondes.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_scheduler_executions(request):
    """Historique des 100 dernières exécutions."""
    if not _can_access_scheduler_admin(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from django_apscheduler.models import DjangoJobExecution

    rows = (
        DjangoJobExecution.objects
        .select_related('job')
        .order_by('-run_time')[:100]
    )
    data = [
        {
            'id':        e.id,
            'job_id':    e.job_id,
            'run_time':  e.run_time,
            'status':    e.status,
            'duration':  float(e.duration) if e.duration else None,
            'exception': e.exception,
        }
        for e in rows
    ]
    return Response(data)
