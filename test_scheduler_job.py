"""
Script pour tester manuellement l'exécution d'un job du scheduler
"""
import os
import sys
import django
from datetime import datetime

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KORA.settings')
django.setup()

print("=" * 70)
print("TEST D'EXÉCUTION MANUELLE D'UN JOB DU SCHEDULER")
print("=" * 70)
print()

try:
    from parametre.scheduler import send_reminders_job, send_dashboard_reminders_job
    
    print("🔄 Test d'exécution du job send_reminders_job...")
    print(f"   Heure actuelle: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Exécuter le job manuellement
    send_reminders_job()
    
    print()
    print("✅ Test terminé avec succès")
    
except Exception as e:
    print(f"❌ Erreur lors du test: {str(e)}")
    import traceback
    traceback.print_exc()

print()
print("=" * 70)
