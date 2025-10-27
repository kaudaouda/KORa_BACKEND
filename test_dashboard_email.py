"""
Script de test pour envoyer un email de notification tableau de bord
"""
import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KORA.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings
from parametre.models import EmailSettings
from django.contrib.auth import get_user_model

User = get_user_model()

def test_dashboard_email():
    """
    Envoie un email de test de notification tableau de bord
    """
    
    # Récupérer la configuration email
    email_settings = EmailSettings.get_solo()
    
    # Vérifier que la configuration est complète
    if not email_settings.email_host_user or not email_settings.email_host_password:
        print("❌ Configuration email incomplète!")
        print("Veuillez configurer EMAIL_HOST_USER et EMAIL_HOST_PASSWORD dans l'admin Django.")
        return
    
    # Appliquer la configuration
    config = email_settings.get_email_config()
    for key, value in config.items():
        setattr(settings, key, value)
    
    # Email de test
    recipient_email = "kaunedaouda@gmail.com"
    
    subject = "KORA - TEST - Rappel Indicateur OB01"
    
    html_body = """
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">KORA - Tableau de bord</h2>
            </div>
            
            <div style="background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px;">
                <p>Bonjour Daouda,</p>
                
                <div style="background: white; padding: 15px; border-left: 4px solid #667eea; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Objectif:</strong> OB01 - Assurer à 70% la mise en œuvre du plan annuel</p>
                    <p style="margin: 5px 0;"><strong>Indicateur:</strong> Taux de mise en œuvre des actions du plan ANAC 2025</p>
                    <p style="margin: 5px 0;"><strong>Fréquence:</strong> Annuelle</p>
                    <p style="margin: 5px 0;"><strong>Période:</strong> Année</p>
                    <p style="margin: 5px 0;"><strong>Date de fin:</strong> 31/12/2024</p>
                    <p style="margin: 5px 0;"><strong>Statut:</strong> ⚠️ La période se termine dans 7 jour(s)</p>
                </div>
                
                <p>Veuillez compléter les données de la période dans KORA.</p>
                
                <div style="text-align: center; margin: 20px 0;">
                    <a href="http://localhost:5173/dashboard" 
                       style="background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Accéder au tableau de bord
                    </a>
                </div>
                
                <p style="color: #666; font-size: 0.9em; margin-top: 30px;">
                    Cordialement,<br>
                    L'équipe KORA
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    text_body = """
    KORA - Tableau de bord

    Bonjour Daouda,

    Objectif: OB01 - Assurer à 70% la mise en œuvre du plan annuel
    Indicateur: Taux de mise en œuvre des actions du plan ANAC 2025
    Fréquence: Annuelle
    Période: Année
    Date de fin: 31/12/2024
    Statut: ⚠️ La période se termine dans 7 jour(s)

    Veuillez compléter les données de la période dans KORA.

    Cordialement,
    L'équipe KORA
    """
    
    try:
        send_mail(
            subject=subject,
            message=text_body,
            html_message=html_body,
            from_email=f"{email_settings.email_from_name} <{email_settings.email_host_user}>",
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        
        print("✅ Email de test envoyé avec succès à:", recipient_email)
        print("\n📧 Détails:")
        print(f"   - De: {email_settings.email_from_name} <{email_settings.email_host_user}>")
        print(f"   - À: {recipient_email}")
        print(f"   - Sujet: {subject}")
        print(f"   - Serveur SMTP: {email_settings.email_host}:{email_settings.email_port}")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi: {str(e)}")
        print("\nVérifiez:")
        print("1. Que les identifiants SMTP sont corrects")
        print("2. Que votre connexion internet fonctionne")
        print("3. Que le serveur SMTP accepte les connexions")


if __name__ == "__main__":
    test_dashboard_email()

