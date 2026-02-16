# Guide de Test du Système de Notifications

## 📋 Étapes pour vérifier que tout fonctionne

### 1. Installation des dépendances

```bash
cd KORa_BACKEND
pip install -r requirements.txt
```

Vérifiez que les packages sont installés :
```bash
pip list | findstr -i "apscheduler"
```

Vous devriez voir :
- `apscheduler==3.10.4`
- `django-apscheduler==0.7.0`

---

### 2. Créer les migrations pour django-apscheduler

```bash
python manage.py migrate
```

Cela créera les tables nécessaires pour le scheduler dans la base de données.

---

### 3. Vérifier la configuration email

Assurez-vous que la configuration email est complète dans l'admin Django :
- Allez dans l'admin : `http://localhost:8000/admin/`
- Vérifiez "Paramètres email" :
  - `EMAIL_HOST_USER` doit être configuré
  - `EMAIL_HOST_PASSWORD` doit être configuré (chiffré)

---

### 4. Vérifier les paramètres de notification

Dans l'admin Django, vérifiez "Paramètres de notification" :
- `Traitement delai notice days` : nombre de jours avant l'échéance (ex: 7)
- `Traitement reminder frequency days` : fréquence des rappels (ex: 1 = chaque jour)

---

### 5. Test manuel des commandes (Mode DRY-RUN)

#### Test 1 : Rappels de traitements
```bash
python manage.py send_reminders_secure --dry-run
```

**Ce que vous devriez voir :**
- ✅ Connexion SMTP OK (si configuré)
- Liste des utilisateurs vérifiés
- Messages indiquant si des emails seraient envoyés
- Aucun email réellement envoyé (mode dry-run)

#### Test 2 : Rappels de tableaux de bord
```bash
python manage.py send_dashboard_reminders --dry-run
```

**Ce que vous devriez voir :**
- Vérification des indicateurs
- Messages indiquant si des notifications seraient envoyées
- Aucun email réellement envoyé

---

### 6. Vérifier que le scheduler démarre

Démarrez le serveur Django :
```bash
python manage.py runserver
```

**Dans les logs, vous devriez voir :**
```
✅ Scheduler démarré avec succès
  - Rappels de traitements: chaque jour à 8h00
  - Rappels de tableaux de bord: chaque jour à 8h30
```

**Si vous voyez une erreur :**
- Vérifiez que les migrations sont faites
- Vérifiez que django_apscheduler est dans INSTALLED_APPS
- Vérifiez les logs pour plus de détails

---

### 7. Vérifier les jobs planifiés dans la base de données

Vous pouvez vérifier que les jobs sont bien enregistrés :
```bash
python manage.py shell
```

Puis dans le shell :
```python
from django_apscheduler.models import DjangoJob
jobs = DjangoJob.objects.all()
for job in jobs:
    print(f"Job: {job.name} - ID: {job.id} - Next run: {job.next_run_time}")
```

---

### 8. Test avec le script de vérification

Exécutez le script de test :
```bash
python test_rappels_system.py
```

**Ce que vous devriez voir :**
- ✅ Configuration email présente
- ✅ Commandes disponibles
- ✅ Connexion SMTP (si configurée)
- ✅ Utilisateurs actifs avec email
- ✅ Paramètres de notification OK

---

### 9. Test réel (sans --dry-run)

⚠️ **ATTENTION** : Ceci enverra de vrais emails !

```bash
python manage.py send_reminders_secure
```

Vérifiez :
- Les emails reçus dans les boîtes de réception
- Les logs dans la table `reminder_email_log` (via l'admin Django)

---

### 10. Vérifier les logs d'envoi

Dans l'admin Django, allez dans "Logs emails de relance" :
- Vous devriez voir les emails envoyés
- Le statut (✅ succès ou ❌ échec)
- La date d'envoi

---

## 🔍 Points de vérification

### ✅ Checklist de fonctionnement

- [ ] Les dépendances sont installées
- [ ] Les migrations sont créées
- [ ] La configuration email est complète
- [ ] Les paramètres de notification sont configurés
- [ ] Les commandes fonctionnent en mode --dry-run
- [ ] Le scheduler démarre sans erreur
- [ ] Les jobs sont enregistrés dans la base de données
- [ ] Les emails sont envoyés (test réel)
- [ ] Les logs sont créés dans la base de données

---

## 🐛 Dépannage

### Problème : "ModuleNotFoundError: No module named 'django_apscheduler'"
**Solution :** `pip install django-apscheduler==0.7.0`

### Problème : "Table 'django_apscheduler_djangojob' doesn't exist"
**Solution :** `python manage.py migrate`

### Problème : "Configuration email incomplète"
**Solution :** Configurez les paramètres email dans l'admin Django

### Problème : Le scheduler ne démarre pas
**Vérifiez :**
- Les logs Django pour les erreurs
- Que `django_apscheduler` est dans INSTALLED_APPS
- Que les migrations sont faites

### Problème : Aucun email reçu
**Vérifiez :**
- La configuration SMTP est correcte
- Les utilisateurs ont des emails valides
- Il y a des traitements/indicateurs à notifier
- La fréquence de rappel est respectée (vérifiez les logs)

---

## 📊 Vérification de la fréquence

Pour vérifier que la fréquence est respectée :

1. Envoyez un email manuellement :
```bash
python manage.py send_reminders_secure
```

2. Réessayez immédiatement :
```bash
python manage.py send_reminders_secure
```

**Résultat attendu :** Le deuxième appel devrait dire "Dernier email envoyé il y a 0 jour(s). Fréquence requise: X jour(s)" et ne pas envoyer d'email.

3. Attendez le nombre de jours configuré dans `traitement_reminder_frequency_days` et réessayez.

---

## 🎯 Test automatique du scheduler

Pour tester que le scheduler fonctionne (sans attendre 8h00) :

1. Modifiez temporairement l'heure dans `scheduler.py` :
   - Changez `hour=8` en `hour=23` (ou l'heure actuelle + 1 minute)
   - Redémarrez le serveur
   - Attendez 1 minute
   - Vérifiez les logs

2. Ou utilisez le shell Django pour déclencher manuellement :
```python
python manage.py shell
```

```python
from parametre.scheduler import send_reminders_job
send_reminders_job()  # Exécute le job manuellement
```

---

## ✅ Résultat attendu

Si tout fonctionne correctement, vous devriez :
1. ✅ Voir le scheduler démarrer dans les logs
2. ✅ Pouvoir exécuter les commandes en mode --dry-run
3. ✅ Recevoir des emails (en test réel)
4. ✅ Voir les logs dans l'admin Django
5. ✅ Respecter la fréquence configurée
