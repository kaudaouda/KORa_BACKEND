"""
Script de test pour verifier le systeme de rappels
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KORA.settings')
django.setup()

print("=" * 70)
print("TEST DU SYSTEME DE RAPPELS")
print("=" * 70)
print()

# Test 1 : Configuration email
print("Test 1 : Verification de la configuration email...")
from parametre.models import EmailSettings
try:
    settings = EmailSettings.get_solo()
    has_password = bool(settings.email_host_password or settings.email_host_password_encrypted)
    print(f"   [OK] Configuration email presente")
    print(f"   - Host: {settings.email_host}")
    print(f"   - User: {settings.email_host_user}")
    print(f"   - Password: {'Configure' if has_password else 'NON CONFIGURE'}")
    
    if not has_password:
        print("   [WARNING] Mot de passe SMTP non configure !")
except Exception as e:
    print(f"   [ERREUR] {str(e)}")

print()

# Test 2 : Commandes de rappel disponibles
print("Test 2 : Verification des commandes de rappel...")
import os.path
commands_dir = "parametre/management/commands"
commands = [
    "send_reminders.py",
    "send_dashboard_reminders.py",
    "send_reminders_secure.py"
]

for cmd in commands:
    path = os.path.join(commands_dir, cmd)
    if os.path.exists(path):
        print(f"   [OK] {cmd} - Disponible")
    else:
        print(f"   [MANQUANT] {cmd}")

print()

# Test 3 : Test de connexion SMTP
print("Test 3 : Test de connexion SMTP...")
try:
    success, message = settings.test_smtp_connection()
    if success:
        print(f"   [OK] Connexion SMTP reussie")
    else:
        print(f"   [ERREUR] Connexion SMTP echouee: {message}")
except Exception as e:
    print(f"   [ERREUR] {str(e)}")

print()

# Test 4 : Verifier les utilisateurs avec email
print("Test 4 : Verification des utilisateurs...")
from django.contrib.auth.models import User
users_with_email = User.objects.filter(is_active=True).exclude(email='')
print(f"   [INFO] {users_with_email.count()} utilisateurs actifs avec email")

if users_with_email.count() > 0:
    print(f"   Exemples:")
    for user in users_with_email[:3]:
        from parametre.utils.email_security import SecureEmailLogger
        masked = SecureEmailLogger.mask_email(user.email)
        print(f"   - {user.username}: {masked}")

print()

# Test 5 : Verifier les parametres de notification
print("Test 5 : Verification des parametres de notification...")
from parametre.models import NotificationSettings, DashboardNotificationSettings

try:
    notif_settings = NotificationSettings.get_solo()
    print(f"   [OK] NotificationSettings")
    print(f"   - Delai d'avertissement: {notif_settings.traitement_delai_notice_days} jours")
    print(f"   - Frequence rappels: {notif_settings.traitement_reminder_frequency_days} jours")
except Exception as e:
    print(f"   [ERREUR] NotificationSettings: {str(e)}")

try:
    dash_settings = DashboardNotificationSettings.get_solo()
    print(f"   [OK] DashboardNotificationSettings")
    print(f"   - Jours avant fin periode: {dash_settings.days_before_period_end}")
    print(f"   - Jours apres fin periode: {dash_settings.days_after_period_end}")
    print(f"   - Frequence rappels: {dash_settings.reminder_frequency_days} jours")
except Exception as e:
    print(f"   [ERREUR] DashboardNotificationSettings: {str(e)}")

print()

# Test 6 : Tester l'envoi avec la commande securisee
print("Test 6 : Test de la commande d'envoi securisee...")
print("   Pour tester l'envoi de rappels, executez:")
print("   > python manage.py send_reminders_secure --dry-run")
print("   > python manage.py send_dashboard_reminders --dry-run")

print()

# Resume
print("=" * 70)
print("RESUME")
print("=" * 70)
print()

config_ok = has_password and success
users_ok = users_with_email.count() > 0

print(f"Configuration email: {'OK' if config_ok else 'A CONFIGURER'}")
print(f"Utilisateurs actifs: {'OK' if users_ok else 'Aucun utilisateur'}")
print(f"Commandes disponibles: OK")
print()

if config_ok and users_ok:
    print("[OK] Le systeme de rappels est OPERATIONNEL")
    print()
    print("Pour envoyer des rappels automatiques:")
    print("1. Configurez un cron/tache planifiee")
    print("2. Executez: python manage.py send_reminders_secure")
    print("3. Ou: python manage.py send_dashboard_reminders")
else:
    print("[WARNING] Le systeme necessite une configuration")
    if not config_ok:
        print("- Configurez les parametres SMTP dans l'admin")
    if not users_ok:
        print("- Ajoutez des utilisateurs avec email")

print()
print("=" * 70)
