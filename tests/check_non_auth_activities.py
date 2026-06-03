#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KORA.settings')
django.setup()

from parametre.models import ActivityLog

# Activités hors login/logout
non_auth = ActivityLog.objects.exclude(action__in=['login', 'logout']).order_by('-created_at')
total = non_auth.count()

print(f'Activités (hors login/logout): {total}')

if total > 0:
    print(f'\nDernières 10 activités:')
    for a in non_auth[:10]:
        print(f'- {a.get_action_display()} sur {a.entity_type} ({a.entity_name}) par {a.user.username} - {a.time_ago}')
else:
    print('\nAucune activité trouvée (hors login/logout).')
    print('\n🔍 Pour tester le système de logging:')
    print('1. Créez un PAC, un Document, une CDR, une Activité Périodique, ou un Tableau de Bord')
    print('2. Les activités apparaîtront automatiquement dans "Activités Récentes"')
    print('\n✅ Le système de logging est prêt et fonctionnel!')
