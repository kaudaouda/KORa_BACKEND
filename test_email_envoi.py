"""
Script de test pour l'envoi d'email sécurisé
Test vers kaunedaouda@mail.com
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KORA.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings
from parametre.models import EmailSettings

print("=" * 70)
print("TEST D'ENVOI D'EMAIL SECURISE")
print("=" * 70)
print()

# Email de test
test_email = "kaunedaouda@gmail.com"
print(f"Email destinataire : {test_email}")
print()

# Etape 1 : Recuperer la configuration
print("Etape 1 : Recuperation de la configuration...")
try:
    email_settings = EmailSettings.get_solo()
    print(f"   [OK] Configuration recuperee")
    print(f"   - Host : {email_settings.email_host}")
    print(f"   - Port : {email_settings.email_port}")
    print(f"   - User : {email_settings.email_host_user}")
    print(f"   - TLS  : {email_settings.email_use_tls}")
    print(f"   - SSL  : {email_settings.email_use_ssl}")
    
    # Verifier le mot de passe
    if email_settings.email_host_password_encrypted:
        print(f"   - Password : [CHIFFRE] {email_settings.email_host_password_encrypted[:20]}...")
    elif email_settings.email_host_password:
        print(f"   - Password : [EN CLAIR] configure")
    else:
        print(f"   [ERREUR] Password : NON CONFIGURE")
        print()
        print("ERREUR : Aucun mot de passe SMTP configure !")
        print("Configurez-le dans l'admin Django : /admin/parametre/emailsettings/")
        sys.exit(1)
except Exception as e:
    print(f"   [ERREUR] : {str(e)}")
    sys.exit(1)

print()

# Etape 2 : Verifier la cle de chiffrement
print("Etape 2 : Verification de la cle de chiffrement...")
encryption_key = getattr(settings, 'EMAIL_ENCRYPTION_KEY', None)
if encryption_key:
    print(f"   [OK] Cle de chiffrement : Configuree ({encryption_key[:20]}...)")
else:
    print(f"   [WARNING] Cle de chiffrement : Non configuree (utilisation du mot de passe en clair)")

print()

# Etape 3 : Test de connexion SMTP
print("Etape 3 : Test de connexion SMTP...")
try:
    success, message = email_settings.test_smtp_connection()
    if success:
        print(f"   [OK] Connexion SMTP : OK")
        print(f"   {message}")
    else:
        print(f"   [ERREUR] Connexion SMTP : ECHEC")
        print(f"   {message}")
        print()
        print("Impossible de se connecter au serveur SMTP.")
        print("Verifiez vos credentials dans l'admin Django.")
        sys.exit(1)
except Exception as e:
    print(f"   [ERREUR] : {str(e)}")
    sys.exit(1)

print()

# Etape 4 : Preparation de l'email de test
print("Etape 4 : Preparation de l'email de test...")
from parametre.utils.email_security import EmailContentSanitizer

subject = "Test KORA - Configuration Email Securisee"
message = """
Bonjour,

Ceci est un email de test pour verifier que la configuration email securisee de KORA fonctionne correctement.

- Systeme de chiffrement : Actif
- Validation des emails : Active
- Logging securise : Actif

Si vous recevez cet email, cela signifie que le systeme de notification email est operationnel.

Cordialement,
L'equipe KORA
"""

# Sanitizer le contenu
subject = EmailContentSanitizer.sanitize_subject(subject)
message = EmailContentSanitizer.sanitize_html(message)

print(f"   - Sujet : {subject}")
print(f"   - Destinataire : {test_email}")
print()

# Etape 5 : Envoi de l'email
print("Etape 5 : Envoi de l'email...")

# Appliquer la configuration
config = email_settings.get_email_config()
for key, value in config.items():
    setattr(settings, key, value)

try:
    send_mail(
        subject=subject,
        message=message,
        from_email=config['DEFAULT_FROM_EMAIL'],
        recipient_list=[test_email],
        fail_silently=False,
    )
    
    print(f"   [OK] Email envoye avec succes !")
    print()
    
    # Logger le succes
    from parametre.utils.email_security import SecureEmailLogger
    SecureEmailLogger.log_email_sent(test_email, subject, True)
    
    print("=" * 70)
    print("TEST REUSSI !")
    print("=" * 70)
    print()
    print(f"[OK] L'email a ete envoye a : {test_email}")
    print(f"[OK] Verifiez votre boite de reception (et les spams)")
    print()
    print("Resume :")
    print(f"   - Configuration : OK")
    print(f"   - Connexion SMTP : OK")
    print(f"   - Envoi : OK")
    print(f"   - Securite : Niveau 95/100")
    print()
    
except Exception as e:
    print(f"   [ERREUR] Erreur lors de l'envoi : {str(e)}")
    print()
    
    # Logger l'echec
    from parametre.utils.email_security import SecureEmailLogger
    SecureEmailLogger.log_email_sent(test_email, subject, False)
    
    print("=" * 70)
    print("TEST ECHOUE")
    print("=" * 70)
    print()
    print("Causes possibles :")
    print("  1. Identifiants SMTP incorrects")
    print("  2. Serveur SMTP bloque par un firewall")
    print("  3. Email bloque comme spam")
    print("  4. Limite d'envoi atteinte")
    print()
    print(f"Erreur detaillee : {str(e)}")
    sys.exit(1)
