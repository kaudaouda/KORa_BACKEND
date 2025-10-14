#!/usr/bin/env python3
"""
Script de test pour l'API Dashboard
"""
import requests
import json

# Configuration
BASE_URL = "http://localhost:8000/api"
DASHBOARD_URL = f"{BASE_URL}/dashboard"

def test_dashboard_api():
    """Tester l'API du tableau de bord"""
    
    print("🧪 Test de l'API Dashboard")
    print("=" * 50)
    
    # Test 1: Récupérer les statistiques
    print("\n1. Test des statistiques...")
    try:
        response = requests.get(f"{DASHBOARD_URL}/stats/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Statistiques récupérées: {data}")
        else:
            print(f"   ❌ Erreur: {response.text}")
    except Exception as e:
        print(f"   ❌ Erreur de connexion: {e}")
    
    # Test 2: Lister les objectifs
    print("\n2. Test de la liste des objectifs...")
    try:
        response = requests.get(f"{DASHBOARD_URL}/objectives/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Objectifs récupérés: {len(data.get('data', []))} objectifs")
        else:
            print(f"   ❌ Erreur: {response.text}")
    except Exception as e:
        print(f"   ❌ Erreur de connexion: {e}")
    
    print("\n" + "=" * 50)
    print("✅ Tests terminés")

if __name__ == "__main__":
    test_dashboard_api()
