#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KORA.settings')
django.setup()

from parametre.models import ActivityLog

total = ActivityLog.objects.count()
print(f'Total activités: {total}')

if total > 0:
    print(f'\nDernières 5 activités:')
    for a in ActivityLog.objects.order_by('-created_at')[:5]:
        print(f'- {a.get_action_display()} sur {a.entity_type} ({a.entity_name}) par {a.user.username} - {a.time_ago}')
else:
    print('\nAucune activité trouvée dans la base de données.')
    print('Créez une activité (PAC, Document, CDR, etc.) pour tester le système de logging.')
