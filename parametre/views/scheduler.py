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



def _extract_job_info(job):
    """Extrait name, hour, minute depuis un DjangoJob via l'API APScheduler (sans pickle)."""
    from apscheduler.triggers.cron import CronTrigger
    from parametre.scheduler import scheduler as _scheduler

    name = hour = minute = None
    try:
        if _scheduler and _scheduler.running:
            live_job = _scheduler.get_job(job.id)
            if live_job:
                name = live_job.name
                trigger = live_job.trigger
                if isinstance(trigger, CronTrigger):
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


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_scheduler_jobs(request):
    """Liste des jobs du scheduler avec trigger info et dernière exécution."""
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
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
    """Modifie l'heure/minute cron d'un job."""
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from django_apscheduler.models import DjangoJob
    from apscheduler.triggers.cron import CronTrigger
    from parametre.scheduler import scheduler as _scheduler

    if not _scheduler or not _scheduler.running:
        return Response({'error': 'Scheduler non actif.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

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

    try:
        _scheduler.reschedule_job(job_id, trigger=CronTrigger(hour=hour, minute=minute))
        logger.info("[SCHEDULER] Job %s reprogrammé à %02d:%02d", job_id, hour, minute)
        job.refresh_from_db()
        return Response(_serialize_job(job))
    except Exception as e:
        logger.error("[SCHEDULER] Erreur reprogrammation job %s: %s", job_id, e, exc_info=True)
        return Response({'error': "Une erreur inattendue s'est produite. Veuillez réessayer."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_scheduler_job_trigger(request, job_id):
    """Déclenche manuellement un job dans un thread séparé."""
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
        return Response({'error': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)

    from parametre.scheduler import scheduler as _scheduler
    import threading

    if not _scheduler or not _scheduler.running:
        return Response({'error': 'Le scheduler n\'est pas actif.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    job = _scheduler.get_job(job_id)
    if not job:
        return Response({'error': 'Job introuvable dans le scheduler.'}, status=status.HTTP_404_NOT_FOUND)

    threading.Thread(target=job.func, daemon=True).start()
    logger.info("[SCHEDULER] Job %s déclenché manuellement par %s", job_id, request.user.username)
    return Response({'message': f'Job « {job.name} » déclenché.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_scheduler_executions(request):
    """Historique des 100 dernières exécutions."""
    from parametre.permissions import can_manage_users
    if not can_manage_users(request.user):
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
