#!/usr/bin/env python
"""
Script pour générer une clé de chiffrement pour le système email
Security by Design - KORA 2026
"""
from cryptography.fernet import Fernet
import os
import sys

def generate_key():
    """Génère une nouvelle clé de chiffrement Fernet"""
    key = Fernet.generate_key()
    return key.decode()

def save_to_env(key, env_file='.env'):
    """Sauvegarde la clé dans le fichier .env"""
    key_line = f"EMAIL_ENCRYPTION_KEY={key}\n"
    
    if os.path.exists(env_file):
        # Lire le fichier existant
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Vérifier si EMAIL_ENCRYPTION_KEY existe déjà
        key_exists = False
        for i, line in enumerate(lines):
            if line.startswith('EMAIL_ENCRYPTION_KEY='):
                print("⚠️  EMAIL_ENCRYPTION_KEY existe déjà dans .env")
                response = input("Voulez-vous le remplacer ? (y/N) : ").strip().lower()
                if response == 'y':
                    lines[i] = key_line
                    key_exists = True
                else:
                    print("❌ Annulé")
                    return False
                break
        
        # Ajouter la clé si elle n'existe pas
        if not key_exists:
            lines.append("\n# Configuration email sécurisée\n")
            lines.append(key_line)
        
        # Écrire le fichier
        with open(env_file, 'w') as f:
            f.writelines(lines)
    else:
        # Créer un nouveau fichier .env
        with open(env_file, 'w') as f:
            f.write("# Configuration email sécurisée\n")
            f.write(key_line)
    
    return True

def main():
    print("=" * 60)
    print("🔒 GÉNÉRATEUR DE CLÉ DE CHIFFREMENT EMAIL - KORA")
    print("=" * 60)
    print()
    
    # Générer la clé
    print("🔑 Génération d'une nouvelle clé de chiffrement...")
    key = generate_key()
    print(f"✅ Clé générée avec succès !\n")
    
    # Afficher la clé
    print("📋 Votre clé de chiffrement :")
    print("-" * 60)
    print(key)
    print("-" * 60)
    print()
    
    # Sauvegarder dans .env
    print("💾 Voulez-vous sauvegarder cette clé dans .env ?")
    response = input("(Y/n) : ").strip().lower()
    
    if response in ['y', 'yes', '']:
        if save_to_env(key):
            print("✅ Clé sauvegardée dans .env")
            print()
            print("⚠️  IMPORTANT : ")
            print("   1. Ne JAMAIS commiter le fichier .env dans Git")
            print("   2. Ajouter .env dans .gitignore")
            print("   3. Sauvegarder cette clé en lieu sûr")
            print("   4. Redémarrer le serveur Django")
        else:
            print()
            print("📝 Copiez manuellement la clé dans votre fichier .env :")
            print(f"   EMAIL_ENCRYPTION_KEY={key}")
    else:
        print()
        print("📝 Copiez manuellement la clé dans votre fichier .env :")
        print(f"   EMAIL_ENCRYPTION_KEY={key}")
    
    print()
    print("=" * 60)
    print("✨ Configuration terminée !")
    print("=" * 60)
    print()
    print("📚 Prochaines étapes :")
    print("   1. Vérifier que .env est dans .gitignore")
    print("   2. Exécuter les migrations : python manage.py migrate")
    print("   3. Tester la configuration : python manage.py send_reminders_secure --dry-run")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Annulé par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Erreur : {str(e)}")
        sys.exit(1)
