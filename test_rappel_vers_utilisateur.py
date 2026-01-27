"""
Test d'envoi de rappel vers kaunedaouda@gmail.com
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KORA.settings')
django.setup()

from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from parametre.models import EmailSettings
from parametre.utils.email_security import EmailContentSanitizer, SecureEmailLogger

print("=" * 70)
print("TEST DE RAPPEL - SIMULATION EMAIL")
print("=" * 70)
print()

# Configuration
test_email = "kaunedaouda@gmail.com"
print(f"Email destinataire : {test_email}")
print()

# Etape 1 : Recuperer la configuration
print("Etape 1 : Configuration email...")
email_settings = EmailSettings.get_solo()
config = email_settings.get_email_config()

# Appliquer la configuration
for key, value in config.items():
    setattr(settings, key, value)

print(f"   [OK] Configuration chargee")
print()

# Etape 2 : Creer un email de rappel realiste
print("Etape 2 : Preparation du rappel...")

subject = "KORA - Rappel : Echeance approchant"

# Email HTML (comme ceux envoyes par le systeme)
html_body = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KORA - Rappel</title>
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #F9FAFB;">
    <div style="max-width: 600px; margin: 0 auto; background: #FFFFFF;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #F97316 0%, #3B82F6 100%); padding: 24px; text-align: center;">
            <h1 style="margin: 0; color: #FFFFFF; font-size: 24px;">KORA</h1>
            <p style="margin: 8px 0 0 0; color: #FFFFFF;">Systeme de gestion</p>
        </div>
        
        <!-- Content -->
        <div style="padding: 24px;">
            <p style="margin: 0 0 16px 0; color: #111827;">
                Bonjour,
            </p>
            
            <p style="margin: 0 0 20px 0; color: #4B5563;">
                Ceci est un email de rappel automatique concernant des echeances approchant dans KORA.
            </p>
            
            <!-- Notification 1 -->
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <div style="width: 4px; height: 20px; background: #F59E0B; border-radius: 2px; margin-right: 12px;"></div>
                    <h3 style="margin: 0; color: #111827; font-size: 16px;">Traitement PAC - Delai approchant</h3>
                </div>
                <p style="margin: 4px 0; color: #4B5563; font-size: 14px;">
                    Le traitement PAC #2024-001 arrive a echeance dans 3 jours.
                </p>
                <div style="margin-top: 12px;">
                    <span style="color: #4B5563; font-size: 13px;">Echeance: <strong>15/01/2026</strong></span>
                </div>
            </div>
            
            <!-- Notification 2 -->
            <div style="background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
                <div style="display: flex; align-items: center; margin-bottom: 8px;">
                    <div style="width: 4px; height: 20px; background: #EF4444; border-radius: 2px; margin-right: 12px;"></div>
                    <h3 style="margin: 0; color: #111827; font-size: 16px;">Indicateur Tableau de Bord - A renseigner</h3>
                </div>
                <p style="margin: 4px 0; color: #4B5563; font-size: 14px;">
                    L'indicateur "Taux de conformite" doit etre renseigne pour la periode en cours.
                </p>
                <div style="margin-top: 12px;">
                    <span style="color: #4B5563; font-size: 13px;">Periode: <strong>Janvier 2026</strong></span>
                </div>
            </div>
            
            <p style="margin: 20px 0 0 0; color: #4B5563; font-size: 14px;">
                Connectez-vous a KORA pour traiter ces echeances.
            </p>
        </div>
        
        <!-- Footer -->
        <div style="background: #F3F4F6; padding: 20px; text-align: center;">
            <p style="margin: 0; color: #6B7280; font-size: 12px;">
                Message automatique envoye par KORA
            </p>
            <p style="margin: 4px 0 0 0; color: #6B7280; font-size: 12px;">
                Systeme de notification securise - Niveau 95/100
            </p>
        </div>
    </div>
</body>
</html>
"""

# Version texte (pour les clients email qui ne supportent pas HTML)
text_body = """
Bonjour,

Ceci est un email de rappel automatique concernant des echeances approchant dans KORA.

1. Traitement PAC - Delai approchant
   Le traitement PAC #2024-001 arrive a echeance dans 3 jours.
   Echeance: 15/01/2026

2. Indicateur Tableau de Bord - A renseigner
   L'indicateur "Taux de conformite" doit etre renseigne pour la periode en cours.
   Periode: Janvier 2026

Connectez-vous a KORA pour traiter ces echeances.

---
Message automatique envoye par KORA
Systeme de notification securise - Niveau 95/100
"""

print(f"   [OK] Email prepare")
print(f"   - Sujet: {subject}")
print(f"   - Destinataire: {test_email}")
print()

# Etape 3 : Envoi
print("Etape 3 : Envoi de l'email...")

try:
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=config['DEFAULT_FROM_EMAIL'],
        to=[test_email]
    )
    email.attach_alternative(html_body, "text/html")
    email.send()
    
    print(f"   [OK] Email envoye avec succes !")
    print()
    
    # Logger le succes
    SecureEmailLogger.log_email_sent(test_email, subject, True)
    
    print("=" * 70)
    print("TEST REUSSI !")
    print("=" * 70)
    print()
    print(f"[OK] Email de rappel envoye a : {test_email}")
    print(f"[OK] Verifiez votre boite de reception Gmail")
    print()
    print("Ce que vous devriez recevoir :")
    print("  - Sujet : KORA - Rappel : Echeance approchant")
    print("  - Contenu : 2 notifications d'exemple")
    print("  - Format : HTML avec design complet")
    print()
    print("Si l'email n'apparait pas :")
    print("  1. Verifiez le dossier SPAM")
    print("  2. Verifiez l'onglet Promotions (Gmail)")
    print("  3. Attendez quelques minutes")
    print()
    
except Exception as e:
    print(f"   [ERREUR] Echec de l'envoi : {str(e)}")
    print()
    
    # Logger l'echec
    SecureEmailLogger.log_email_sent(test_email, subject, False)
    
    print("=" * 70)
    print("TEST ECHOUE")
    print("=" * 70)
    print()
    print(f"Erreur detaillee : {str(e)}")
    sys.exit(1)
