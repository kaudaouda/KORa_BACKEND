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
    Extrait (hour, minute, name, trigger) depuis un DjangoJob.

    Priorité 1 : scheduler live en mémoire (disponible uniquement dans le process
                 du service kora-scheduler, pas dans les workers Gunicorn).
    Priorité 2 : pickle job_state stocké dans la DB — toujours disponible.

    Le trigger est renvoyé en plus de (hour, minute) pour permettre de calculer
    next_run_time à la volée (voir _serialize_job) : la colonne DjangoJob.next_run_time
    n'est resynchronisée que par le service scheduler séparé, de façon asynchrone
    (jusqu'à 30s de délai, et pas du tout si ce service est indisponible) —
    la calculer depuis le trigger réel évite tout affichage périmé.
    """
    import pickle
    from apscheduler.triggers.cron import CronTrigger
    from parametre.scheduler import scheduler as _scheduler

    name = hour = minute = trigger = None

    # Priorité 1 : scheduler live
    try:
        if _scheduler and _scheduler.running:
            live_job = _scheduler.get_job(job.id)
            if live_job:
                name = live_job.name
                trigger = live_job.trigger
                hour, minute = _read_cron_fields(trigger)
                return hour, minute, name, trigger
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
                trigger = job_state.get('trigger')
                hour, minute = _read_cron_fields(trigger)
        except Exception:
            pass

    return hour, minute, name, trigger


def _serialize_job(job):
    from django_apscheduler.models import DjangoJobExecution
    from django.utils import timezone
    hour, minute, name, trigger = _extract_job_info(job)

    next_run_time = job.next_run_time
    if trigger is not None:
        try:
            computed = trigger.get_next_fire_time(None, timezone.now())
            if computed is not None:
                next_run_time = computed
        except Exception:
            pass

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
        'next_run_time': next_run_time,
        'hour':          hour,
        'minute':        minute,
        'last_execution': last_exec,
    }


def _can_access_scheduler_admin(user):
    """Seul le superadmin Django (is_staff + is_superuser) peut gérer le scheduler."""
    from parametre.permissions import can_manage_users
    result = can_manage_users(user)
    # DIAG TEMPORAIRE — à retirer une fois le bug 403 scheduler résolu.
    logger.warning(
        "[SCHEDULER][DIAG] user=%r is_authenticated=%s is_staff=%s is_superuser=%s can_manage_users=%s",
        user,
        getattr(user, 'is_authenticated', None),
        getattr(user, 'is_staff', None),
        getattr(user, 'is_superuser', None),
        result,
    )
    return result


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_scheduler_jobs(request):
    """Liste des jobs du scheduler avec trigger info et dernière exécution."""
    if not _can_access_scheduler_admin(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from django_apscheduler.models import DjangoJob
    from parametre.scheduler import is_scheduler_service_running

    jobs = DjangoJob.objects.all().order_by('id')
    scheduler_running = is_scheduler_service_running()
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
    from django_apscheduler.models import DjangoJob
    from parametre.scheduler import write_scheduler_command, rebuild_cron_trigger

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

    # 1. Mettre à jour le pickle en DB pour cohérence immédiate du GET.
    #    rebuild_cron_trigger préserve les champs existants du trigger (day_of_week,
    #    day, month...) : sans ça, un simple changement d'heure sur un job
    #    hebdomadaire le transformerait silencieusement en job quotidien.
    if job.job_state:
        try:
            job_state = (
                pickle.loads(job.job_state)
                if isinstance(job.job_state, bytes)
                else job.job_state
            )
            if isinstance(job_state, dict):
                job_state['trigger'] = rebuild_cron_trigger(job_state.get('trigger'), hour, minute)
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
