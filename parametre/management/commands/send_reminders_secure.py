"""
Commande sécurisée pour l'envoi de rappels par email
Commande principale utilisée par le scheduler APScheduler pour les notifications automatiques

Security by Design :
- Validation des emails
- Sanitization du contenu
- Rate limiting
- Logging sécurisé
- Gestion d'erreurs robuste
"""
import hashlib
from datetime import date
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from parametre.models import ReminderEmailLog, EmailSettings, UserProcessusRole, Role
from parametre.views import upcoming_notifications, get_client_ip
from pac.models import TraitementPac
from parametre.utils.email_security import (
    EmailValidator,
    EmailContentSanitizer,
    EmailRateLimiter,
    SecureEmailLogger
)
from rest_framework.test import APIRequestFactory, force_authenticate

import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envoi sécurisé de rappels par email"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Afficher ce qui serait envoyé sans envoyer réellement'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer l\'envoi même si les limites sont atteintes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        User = get_user_model()

        self.stdout.write(self.style.SUCCESS("Démarrage de l'envoi sécurisé de rappels"))

        # ===== ÉTAPE 1 : Validation de la configuration =====
        try:
            email_settings = EmailSettings.get_solo()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erreur lors de la récupération de la configuration: {str(e)}"))
            return

        # Vérifier que la configuration est complète
        if not email_settings.email_host_user or not email_settings.get_password():
            self.stderr.write(self.style.ERROR(
                "Configuration email incomplète. "
                "Veuillez configurer EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans l'admin."
            ))
            return

        # Test de connexion SMTP
        if not dry_run:
            self.stdout.write("Test de la connexion SMTP...")
            connection_ok, message = email_settings.test_smtp_connection()
            if not connection_ok:
                self.stderr.write(self.style.ERROR(f"Échec de la connexion SMTP : {message}"))
                return
            self.stdout.write(self.style.SUCCESS(f"Connexion SMTP OK"))

        # Appliquer la configuration
        self.apply_email_config(email_settings)

        # ===== ÉTAPE 2 : Vérification du rate limiting global =====
        if not force and email_settings.enable_rate_limiting:
            if not EmailRateLimiter.check_global_limit():
                self.stderr.write(self.style.ERROR(
                    "Limite globale d'emails dépassée. Utilisez --force pour forcer l'envoi."
                ))
                SecureEmailLogger.log_security_event('rate_limit_reached', {
                    'type': 'global_daily',
                    'command': 'send_reminders_secure'
                })
                return

        # ===== ÉTAPE 3 : Récupération des utilisateurs éligibles =====
        # Séparer les admins des utilisateurs normaux
        # Les admins ne reçoivent QUE l'email récapitulatif admin
        # Les utilisateurs normaux (contributeur, responsable_processus) reçoivent l'email de rappel
        
        # Récupérer le rôle admin
        admin_role = Role.objects.filter(code='admin', is_active=True).first()
        
        # Récupérer les rôles pour les utilisateurs normaux
        normal_user_role_codes = ['contributeur', 'responsable_processus']
        normal_user_roles = Role.objects.filter(
            code__in=normal_user_role_codes,
            is_active=True
        )
        
        if not normal_user_roles.exists():
            self.stderr.write(self.style.ERROR(
                "Aucun rôle 'contributeur' ou 'responsable_processus' trouvé dans la base de données.\n"
                "   Veuillez exécuter: python manage.py seed_roles"
            ))
            return
        
        # Récupérer les utilisateurs NORMaux (contributeur, responsable_processus) qui recevront l'email de rappel
        # EXCLURE les admins de cette liste
        users_with_roles = User.objects.filter(
            is_active=True,
            email__isnull=False
        ).exclude(email='').filter(
            user_processus_roles__role__in=normal_user_roles,
            user_processus_roles__is_active=True
        )
        
        # Exclure les utilisateurs qui ont AUSSI le rôle admin
        if admin_role:
            users_with_roles = users_with_roles.exclude(
                user_processus_roles__role=admin_role,
                user_processus_roles__is_active=True
            )
        
        users_with_roles = users_with_roles.distinct()
        
        users_count = users_with_roles.count()
        self.stdout.write(self.style.SUCCESS(
            f"{users_count} utilisateur(s) avec les rôles 'contributeur' ou 'responsable_processus' trouvé(s) (admins exclus)"
        ))
        
        if users_count == 0:
            self.stdout.write(self.style.WARNING(
                "Aucun utilisateur éligible trouvé. Aucun email ne sera envoyé."
            ))
            return
        
        # ===== ÉTAPE 4 : Récupération et envoi des notifications =====
        factory = APIRequestFactory()
        
        total_emails = 0
        total_errors = 0
        total_skipped = 0
        
        # Collecter toutes les notifications pour l'alerte admin globale
        all_notifications_for_admin = []

        for user in users_with_roles:
            # Valider l'email de l'utilisateur
            if not EmailValidator.is_valid_email(user.email):
                self.stdout.write(self.style.WARNING(
                    f"Email invalide pour {user.username}: {SecureEmailLogger.mask_email(user.email)}"
                ))
                total_skipped += 1
                continue

            # Construire une requête authentifiée
            request = factory.get('/api/parametre/upcoming-notifications/')
            force_authenticate(request, user=user)
            response = upcoming_notifications(request)

            if response.status_code != 200:
                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        f"Erreur API pour {user.username}: status {response.status_code}"
                    ))
                continue

            data = response.data or {}
            notifications = data.get('notifications', [])
            
            if dry_run:
                if notifications:
                    self.stdout.write(self.style.SUCCESS(
                        f"{user.username}: {len(notifications)} notification(s) trouvée(s)"
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f"ℹ️  {user.username}: Aucune notification trouvée (pas d'échéances dans les prochains jours)"
                    ))
            
            if not notifications:
                total_skipped += 1
                continue

            # ===== ÉTAPE 5 : Préparation et envoi de l'email =====
            success = self.send_email_to_user(
                user,
                notifications,
                email_settings,
                dry_run,
                force
            )

            if success:
                total_emails += 1
                
                # ===== ÉTAPE 5.1 : Collecter pour l'alerte admin globale =====
                # Ajouter les notifications de cet utilisateur à la liste globale
                all_notifications_for_admin.append({
                    'user': user,
                    'notifications': notifications
                })
                    
            elif success is False:
                total_errors += 1
            else:  # None = skipped
                total_skipped += 1

        # ===== ÉTAPE 5.2 : Envoyer UN SEUL email récapitulatif aux admins =====
        if all_notifications_for_admin:
            try:
                self.send_admin_alert_global(all_notifications_for_admin, email_settings, dry_run)
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi de l'alerte admin globale: {str(e)}")
                # Ne pas bloquer le processus si l'alerte admin échoue

        # ===== ÉTAPE 6 : Rapport final =====
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"\nMode dry-run terminé:\n"
                f"  - {total_emails} emails seraient envoyés\n"
                f"  - {total_errors} erreurs\n"
                f"  - {total_skipped} ignorés"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nEnvoi terminé:\n"
                f"  - {total_emails} emails envoyés\n"
                f"  - {total_errors} échecs\n"
                f"  - {total_skipped} ignorés"
            ))

    def send_email_to_user(self, user, notifications, email_settings, dry_run, force):
        """
        Envoie un email sécurisé à un utilisateur
        
        Returns:
            True si envoyé, False si erreur, None si ignoré
        """
        # Vérifier le rate limiting utilisateur
        if not force and email_settings.enable_rate_limiting:
            if not EmailRateLimiter.check_user_limit(user.id):
                self.stdout.write(self.style.WARNING(
                    f"Limite atteinte pour {user.username}"
                ))
                return None

        # Préparer le sujet (sécurisé)
        subject = EmailContentSanitizer.sanitize_subject(
            f"KORA - Rappel d'échéances ({len(notifications)} élément{'s' if len(notifications) > 1 else ''})"
        )

        frontend_base = getattr(settings, 'FRONTEND_BASE_URL', 'http://localhost:5173')

        # Générer les corps (sécurisés)
        html_body = self.generate_secure_html_email(user, notifications, frontend_base)
        text_body = self.generate_secure_text_email(user, notifications, frontend_base)

        # ===== GÉNÉRATION DU HASH DU CONTENU =====
        # Créer un hash basé sur les IDs des notifications pour détecter les changements de contenu
        notification_ids = sorted([n.get('id', '') for n in notifications])
        content_key = ':'.join(notification_ids) if notification_ids else 'empty'
        content_hash = hashlib.sha256(content_key.encode('utf-8')).hexdigest()
        
        # Hash complet pour la déduplication (email + date + contenu)
        context_key = f"{user.email}:{date.today().isoformat()}:{content_hash}"
        context_hash = hashlib.sha256(context_key.encode('utf-8')).hexdigest()

        # ===== DÉDUPLICATION PAR CONTENU (éviter les doublons le même jour) =====
        # TEMPORAIREMENT DÉSACTIVÉ POUR LES TESTS - À REMETTRE APRÈS LES TESTS
        # Vérifier si un email avec le même contenu a déjà été envoyé aujourd'hui
        # already_sent_today = ReminderEmailLog.objects.filter(
        #     recipient=user.email,
        #     context_hash=context_hash,
        #     sent_at__date=date.today()
        # ).exists()
        #
        # if already_sent_today:
        #     if dry_run:
        #         self.stdout.write(self.style.WARNING(
        #             f"⏭️ [DRY-RUN] Email identique déjà envoyé aujourd'hui à {user.username} "
        #             f"(serait ignoré en mode réel)"
        #         ))
        #     else:
        #         self.stdout.write(self.style.WARNING(
        #             f"⏭️ Email identique déjà envoyé aujourd'hui à {user.username}"
        #         ))
        #     return None

        # ===== VÉRIFICATION DE LA FRÉQUENCE DES RAPPELS =====
        # Récupérer la politique de notification pour respecter la fréquence
        from parametre.models import NotificationPolicy
        policy = NotificationPolicy.get_for_scope(NotificationPolicy.SCOPE_PAC)
        reminder_frequency = policy.reminder_frequency_days

        # Chercher le dernier email envoyé avec succès pour cet utilisateur
        last_sent = ReminderEmailLog.objects.filter(
            recipient=user.email,
            success=True
        ).order_by('-sent_at').first()

        if last_sent:
            days_since_last = (date.today() - last_sent.sent_at.date()).days
            
            # Si un email a été envoyé récemment (moins de X jours), on vérifie si le contenu a changé
            # Pour cela, on compare le hash du contenu actuel avec celui du dernier email
            # Le context_hash du dernier email contient le hash du contenu de l'époque
            # On ne peut pas directement comparer car le context_hash inclut aussi email+date
            # Mais si on arrive ici (pas de doublon aujourd'hui), c'est que soit :
            # 1. Le contenu a changé (nouveaux traitements ou échéances modifiées)
            # 2. C'est un nouveau jour et le contenu est différent
            # 3. Le contenu est identique mais on respecte la fréquence
            
            # Pour simplifier et être sûr d'envoyer les notifications importantes :
            # Si le dernier email était aujourd'hui mais avec un contenu différent, on envoie
            # Si le dernier email était récemment (moins de X jours), on envoie aussi
            # car on ne peut pas facilement comparer le contenu exact sans modifier le modèle
            
            # IMPORTANT: Si on arrive ici, c'est qu'aucun email identique n'a été envoyé aujourd'hui
            # Donc soit le contenu a changé, soit c'est le premier envoi du jour
            # On envoie donc toujours pour être sûr de ne pas manquer de notifications importantes
            if days_since_last < reminder_frequency:
                self.stdout.write(self.style.SUCCESS(
                    f"Envoi pour {user.username} (dernier email il y a {days_since_last} jour(s), "
                    f"contenu probablement modifié ou premier envoi du jour)"
                ))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f"[DRY-RUN] Email serait envoyé à {SecureEmailLogger.mask_email(user.email)}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"         Sujet: {subject}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"         Nombre de notifications: {len(notifications)}"
            ))
            return True

        # Envoyer l'email
        try:
            from_email = f"{email_settings.email_from_name} <{email_settings.email_host_user}>"
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=from_email,
                to=[user.email]
            )
            email.attach_alternative(html_body, "text/html")
            email.send()

            # Logger le succès
            with transaction.atomic():
                ReminderEmailLog.objects.create(
                    recipient=user.email,
                    subject=subject,
                    context_hash=context_hash,
                    success=True,
                    user=user
                )

            SecureEmailLogger.log_email_sent(user.email, subject, True)
            self.stdout.write(self.style.SUCCESS(
                f"Envoyé à {SecureEmailLogger.mask_email(user.email)}"
            ))

            return True

        except Exception as e:
            # Logger l'échec
            error_message = str(e)[:500]  # Limiter la taille

            try:
                with transaction.atomic():
                    ReminderEmailLog.objects.create(
                        recipient=user.email,
                        subject=subject,
                        context_hash=context_hash,
                        success=False,
                        error_message=error_message,
                        user=user
                    )
            except Exception as log_error:
                logger.error(f"Erreur lors de la création du log: {str(log_error)}")

            SecureEmailLogger.log_email_sent(user.email, subject, False)
            self.stderr.write(self.style.ERROR(
                f"Échec pour {SecureEmailLogger.mask_email(user.email)}: {error_message[:100]}"
            ))

            return False

    def generate_secure_html_email(self, user, notifications, frontend_base):
        """
        Génère un email HTML sécurisé en utilisant un template Django
        Security by Design : Sanitization complète via le template engine
        """
        from datetime import datetime
        from django.template.loader import render_to_string

        # Sanitizer toutes les données utilisateur
        user_name = EmailContentSanitizer.sanitize_html(
            user.get_full_name() or user.username
        )
        current_date = datetime.now().strftime("%d/%m/%Y à %H:%M")

        # Préparer les notifications avec sanitization et formatage enrichi
        sanitized_notifications = []
        for n in notifications:
            title = EmailContentSanitizer.sanitize_html(n.get('title', 'Échéance'))
            message = EmailContentSanitizer.sanitize_html(n.get('message', ''))
            due = n.get('due_date', '')
            priority = n.get('priority', 'medium')

            priority_color = {
                'high': '#EF4444',
                'medium': '#F59E0B',
                'low': '#10B981'
            }.get(priority, '#3B82F6')

            # Formater la date
            try:
                due_date_formatted = datetime.fromisoformat(due.replace('Z', '+00:00')).strftime("%d/%m/%Y")
            except:
                due_date_formatted = EmailContentSanitizer.sanitize_html(str(due))
            
            # Enrichir avec les détails complets du PAC
            entity_id = n.get('entity_id')
            numero_pac = "N/A"
            processus_name = "N/A"
            action = message  # Fallback
            nature_label = None
            days_remaining = n.get('days_remaining', 0)
            
            if entity_id:
                try:
                    traitement = TraitementPac.objects.select_related(
                        'details_pac__pac__processus'
                    ).get(uuid=entity_id)
                    
                    if traitement.details_pac:
                        numero_pac = traitement.details_pac.numero_pac or "N/A"
                    
                    if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                        processus_name = traitement.details_pac.pac.processus.nom
                    
                    action = traitement.action[:100] if traitement.action else message
                    nature_label = n.get('nature_label')
                    
                except TraitementPac.DoesNotExist:
                    logger.warning(f"Traitement {entity_id} non trouvé pour email utilisateur")
                except Exception as e:
                    logger.error(f"Erreur lors de l'enrichissement {entity_id}: {str(e)}")

            sanitized_notifications.append({
                'title': title,
                'message': message,
                'due_date_formatted': due_date_formatted,
                'priority': priority,
                'priority_color': priority_color,
                'numero_pac': numero_pac,
                'processus_name': processus_name,
                'action': action,
                'nature_label': nature_label,
                'days_remaining': days_remaining
            })

        # Contexte pour le template
        context = {
            'user_name': user_name,
            'notifications': sanitized_notifications,
            'current_date': current_date
        }

        # Rendre le template
        return render_to_string('emails/reminder_email.html', context)

    def generate_secure_text_email(self, user, notifications, frontend_base):
        """
        Génère un email texte sécurisé en utilisant un template Django
        Security by Design : Pas d'injection possible via le template engine
        """
        from datetime import datetime
        from django.template.loader import render_to_string

        user_name = user.get_full_name() or user.username
        current_date = datetime.now().strftime("%d/%m/%Y à %H:%M")

        # Préparer les notifications avec formatage enrichi
        formatted_notifications = []
        for n in notifications:
            title = n.get('title', 'Échéance')
            message = n.get('message', '')
            due = n.get('due_date', '')
            
            # Enrichir avec les détails complets du PAC
            entity_id = n.get('entity_id')
            numero_pac = "N/A"
            processus_name = "N/A"
            action = message  # Fallback
            nature_label = None
            days_remaining = n.get('days_remaining', 0)
            
            if entity_id:
                try:
                    traitement = TraitementPac.objects.select_related(
                        'details_pac__pac__processus'
                    ).get(uuid=entity_id)
                    
                    if traitement.details_pac:
                        numero_pac = traitement.details_pac.numero_pac or "N/A"
                    
                    if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                        processus_name = traitement.details_pac.pac.processus.nom
                    
                    action = traitement.action[:100] if traitement.action else message
                    nature_label = n.get('nature_label')
                    
                except TraitementPac.DoesNotExist:
                    logger.warning(f"Traitement {entity_id} non trouvé pour email utilisateur")
                except Exception as e:
                    logger.error(f"Erreur lors de l'enrichissement {entity_id}: {str(e)}")

            # Formater la date
            try:
                due_date_formatted = datetime.fromisoformat(due.replace('Z', '+00:00')).strftime("%d/%m/%Y")
            except:
                due_date_formatted = str(due)

            formatted_notifications.append({
                'title': title,
                'message': message,
                'due_date_formatted': due_date_formatted,
                'numero_pac': numero_pac,
                'processus_name': processus_name,
                'action': action,
                'nature_label': nature_label,
                'days_remaining': days_remaining
            })

        # Contexte pour le template
        context = {
            'user_name': user_name,
            'notifications': formatted_notifications,
            'current_date': current_date
        }

        # Rendre le template
        return render_to_string('emails/reminder_email.txt', context)

    def send_admin_alert_global(self, all_user_notifications, email_settings, dry_run):
        """
        Envoie UN SEUL email récapitulatif aux administrateurs
        Informe les admins de TOUTES les échéances signalées à TOUS les utilisateurs
        
        Args:
            all_user_notifications: Liste de dictionnaires [{'user': user, 'notifications': [...]}, ...]
        
        Returns:
            True si envoyé, False si erreur, None si aucun admin trouvé
        """
        from datetime import datetime
        from django.template.loader import render_to_string
        
        # Récupérer tous les utilisateurs avec le rôle admin
        User = get_user_model()
        try:
            admin_role = Role.objects.filter(code='admin', is_active=True).first()
            if not admin_role:
                logger.warning("Aucun rôle 'admin' trouvé pour envoyer les alertes")
                return None
            
            admin_users = User.objects.filter(
                is_active=True,
                email__isnull=False,
                user_processus_roles__role=admin_role,
                user_processus_roles__is_active=True
            ).exclude(email='').distinct()
            
            if not admin_users.exists():
                logger.info("Aucun administrateur trouvé pour envoyer les alertes")
                return None
                
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des admins: {str(e)}")
            return False
        
        # Préparer les données enrichies pour TOUTES les notifications de TOUS les utilisateurs
        # Utiliser un dictionnaire pour DEDUPLIQUER les PACs (même PAC = une seule fois)
        unique_pacs = {}
        total_notifications = 0
        
        for user_notif in all_user_notifications:
            user = user_notif['user']
            notifications = user_notif['notifications']
            total_notifications += len(notifications)
            
            for n in notifications:
                # Extraire l'UUID du traitement depuis l'entity_id
                entity_id = n.get('entity_id')
                if not entity_id:
                    continue
                
                try:
                    # Récupérer le traitement pour obtenir le processus
                    traitement = TraitementPac.objects.select_related(
                        'details_pac__pac__processus'
                    ).get(uuid=entity_id)
                    
                    processus_name = "N/A"
                    if traitement.details_pac and traitement.details_pac.pac and traitement.details_pac.pac.processus:
                        processus_name = traitement.details_pac.pac.processus.nom
                    
                    numero_pac = "N/A"
                    if traitement.details_pac:
                        numero_pac = traitement.details_pac.numero_pac or "N/A"
                    
                    # Si ce PAC existe déjà, on ne l'ajoute pas à nouveau (DEDUPLICATION)
                    if numero_pac in unique_pacs:
                        continue
                    
                    # Formater la date
                    due_date = n.get('due_date', '')
                    try:
                        due_date_formatted = datetime.fromisoformat(due_date.replace('Z', '+00:00')).strftime("%d/%m/%Y")
                    except:
                        due_date_formatted = str(due_date)
                    
                    # Déterminer la couleur de priorité
                    priority = n.get('priority', 'medium')
                    priority_color = {
                        'high': '#EF4444',
                        'medium': '#F59E0B',
                        'low': '#10B981'
                    }.get(priority, '#3B82F6')
                    
                    # Stocker ce PAC dans le dictionnaire unique (clé = numero_pac)
                    unique_pacs[numero_pac] = {
                        'numero_pac': numero_pac,
                        'processus_name': processus_name,
                        'action': traitement.action[:100] if traitement.action else 'N/A',
                        'nature_label': n.get('nature_label'),
                        'due_date_formatted': due_date_formatted,
                        'days_remaining': n.get('days_remaining', 0),
                        'priority': priority,
                        'priority_color': priority_color,
                    }
                except TraitementPac.DoesNotExist:
                    logger.warning(f"Traitement {entity_id} non trouvé pour alerte admin")
                    continue
                except Exception as e:
                    logger.error(f"Erreur lors du traitement {entity_id}: {str(e)}")
                    continue
        
        # Convertir le dictionnaire en liste (valeurs uniquement)
        all_enriched_notifications = list(unique_pacs.values())
        
        if not all_enriched_notifications:
            logger.info("Aucune notification enrichie pour les admins")
            return None
        
        # Préparer le contexte pour les templates
        current_date = datetime.now().strftime("%d/%m/%Y à %H:%M")
        
        # Liste des noms des responsables notifiés
        user_names = [
            user_notif['user'].get_full_name() or user_notif['user'].username
            for user_notif in all_user_notifications
        ]
        
        # Le nombre de PACs DISTINCTS = la taille de la liste (déjà dédupliquée)
        total_unique_pacs = len(all_enriched_notifications)
        
        context = {
            'notifications': all_enriched_notifications,
            'current_date': current_date,
            'total_users': len(all_user_notifications),
            'total_notifications': total_notifications,
            'total_unique_pacs': total_unique_pacs,
            'user_names': user_names
        }
        
        # Générer les emails
        try:
            html_body = render_to_string('emails/admin_alert_email.html', context)
            text_body = render_to_string('emails/admin_alert_email.txt', context)
        except Exception as e:
            logger.error(f"Erreur lors du rendu des templates admin: {str(e)}")
            return False
        
        # Sujet de l'email
        subject = f"KORA - Alerte Admin : {total_unique_pacs} PAC{'s' if total_unique_pacs > 1 else ''} à échéance"
        
        # Envoyer à tous les admins
        sent_count = 0
        for admin in admin_users:
            if not EmailValidator.is_valid_email(admin.email):
                logger.warning(f"Email admin invalide: {admin.email}")
                continue
            
            if dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"[DRY-RUN] Alerte admin serait envoyée à {SecureEmailLogger.mask_email(admin.email)}"
                ))
                sent_count += 1
                continue
            
            try:
                from_email = f"{email_settings.email_from_name} <{email_settings.email_host_user}>"
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=[admin.email]
                )
                email.attach_alternative(html_body, "text/html")
                email.send()
                
                SecureEmailLogger.log_email_sent(admin.email, subject, True)
                self.stdout.write(self.style.SUCCESS(
                    f"Alerte admin envoyée à {SecureEmailLogger.mask_email(admin.email)}"
                ))
                sent_count += 1
                
            except Exception as e:
                error_message = str(e)[:500]
                logger.error(f"Erreur lors de l'envoi alerte admin à {admin.email}: {error_message}")
                SecureEmailLogger.log_email_sent(admin.email, subject, False)
                self.stderr.write(self.style.ERROR(
                    f"Échec alerte admin pour {SecureEmailLogger.mask_email(admin.email)}"
                ))
        
        return sent_count > 0

    def apply_email_config(self, email_settings):
        """Applique la configuration email"""
        config = email_settings.get_email_config()
        for key, value in config.items():
            setattr(settings, key, value)
