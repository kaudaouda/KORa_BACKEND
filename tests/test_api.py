#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'KORA.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from parametre.views import recent_activities

User = get_user_model()

# Créer une fausse requête
factory = RequestFactory()
request = factory.get('/api/parametre/activities/recent/?limit=5')

# Obtenir l'utilisateur
try:
    user = User.objects.first()
    request.user = user

    # Appeler la vue
    response = recent_activities(request)

    # Rendre la réponse si nécessaire
    if hasattr(response, 'render'):
        response.render()

    print(f"Status: {response.status_code}")
    print(f"\nRéponse:")
    import json
    data = json.loads(response.content)
    print(json.dumps(data, indent=2, ensure_ascii=False))

    if data.get('success') and data.get('data'):
        print(f"\n✅ L'API retourne {len(data['data'])} activités")
        print("\nPremière activité:")
        if len(data['data']) > 0:
            first = data['data'][0]
            print(f"- Action: {first['action']}")
            print(f"- Entity type: {first['entity_type']}")
            print(f"- Description: {first['description']}")
    else:
        print("\n❌ Problème avec la réponse de l'API")

except Exception as e:
    print(f"Erreur: {e}")
    import traceback
    traceback.print_exc()
