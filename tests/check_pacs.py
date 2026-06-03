#!/usr/bin/env python
"""
Script de diagnostic pour vérifier les PACs dans la base de données
"""
import os
import sys
import django

# Configuration Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kora_backend.settings')
django.setup()

from pac.models import Pac
from django.contrib.auth.models import User

print("=" * 80)
print("DIAGNOSTIC DES PACs")
print("=" * 80)

# Compter tous les PACs
total_pacs = Pac.objects.count()
print(f"\n📊 Nombre total de PACs dans la base: {total_pacs}")

if total_pacs == 0:
    print("\n⚠️  Aucun PAC trouvé dans la base de données.")
    print("   Vous devez créer un PAC via l'interface ou l'admin Django.")
else:
    print(f"\n✅ {total_pacs} PAC(s) trouvé(s)")
    print("\nDétails des PACs:\n")

    for pac in Pac.objects.all():
        print(f"  🔹 PAC UUID: {pac.uuid}")
        print(f"     - Créé par: {pac.cree_par.username if pac.cree_par else 'NULL (⚠️  PROBLÈME!)'}")
        print(f"     - Processus: {pac.processus.nom if pac.processus else 'NULL'}")
        print(f"     - Année: {pac.annee.annee if pac.annee else 'NULL'}")
        print(f"     - Type tableau: {pac.type_tableau.nom if pac.type_tableau else 'NULL'}")
        print(f"     - Validé: {'Oui' if pac.is_validated else 'Non'}")
        print()

# Lister les utilisateurs
print("\n" + "=" * 80)
print("UTILISATEURS DISPONIBLES")
print("=" * 80)
users = User.objects.all()
print(f"\n👥 Nombre d'utilisateurs: {users.count()}\n")
for user in users:
    pacs_count = Pac.objects.filter(cree_par=user).count()
    print(f"  • {user.username} (ID: {user.id}) - {pacs_count} PAC(s)")

print("\n" + "=" * 80)
print("FIN DU DIAGNOSTIC")
print("=" * 80)
