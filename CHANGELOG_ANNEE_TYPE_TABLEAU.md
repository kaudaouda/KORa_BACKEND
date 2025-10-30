# Changelog - Ajout des modèles Année et Type de Tableau au PAC

## 📝 Résumé

Ajout de deux nouvelles relations au modèle PAC :
- **Année** : Pour filtrer les PAC par année
- **Type de Tableau** : Pour catégoriser les PAC (Initial, Amendement 1, Amendement 2)

## 🎯 Modifications apportées

### 1. Modèles (`parametre/models.py`)

#### ✅ Modèle `Annee` créé
- **Champs** :
  - `uuid` : Identifiant unique
  - `annee` : Année (ex: 2024, 2025) - unique
  - `libelle` : Libellé optionnel (ex: "Année fiscale 2024")
  - `description` : Description optionnelle
  - `is_active` : Statut actif/inactif
  - `created_at`, `updated_at` : Horodatage

- **Relations** :
  - Relation inverse `pacs` vers le modèle PAC

#### ✅ Modèle `Pac` mis à jour (`pac/models.py`)
Ajout de deux nouveaux champs :
- `annee` : ForeignKey vers `parametre.Annee` (nullable, SET_NULL)
- `type_tableau` : ForeignKey vers `parametre.TypeTableau` (nullable, SET_NULL)

### 2. Migrations

#### ✅ Migration `parametre/0035_add_annee_model.py`
- Ajout du champ `libelle` au modèle Annee
- Modification du champ `is_active`

#### ✅ Migration `pac/0011_add_annee_and_type_tableau_to_pac.py`
- Ajout du champ `annee` au modèle Pac
- Ajout du champ `type_tableau` au modèle Pac
- Modification du champ `numero_pac`
- Suppression du modèle obsolète `PlanActionConformite`

### 3. Admin Django

#### ✅ `parametre/admin.py`
- Ajout de `AnneeAdmin` avec :
  - Liste : `annee`, `libelle`, `is_active`, `pacs_count`, `created_at`
  - Filtres : `is_active`, `created_at`, `updated_at`
  - Recherche : `annee`, `libelle`, `description`
  - Tri par défaut : années décroissantes

#### ✅ `pac/admin.py`
- Mise à jour de `PacAdmin` :
  - Ajout de `annee` et `type_tableau` dans `list_display`
  - Ajout de filtres pour ces champs
  - Organisation en sections (fieldsets) :
    - Informations générales
    - Classification (avec année et type_tableau)
    - Période
    - Métadonnées

### 4. Serializers

#### ✅ `parametre/serializers.py`
- `TypeTableauSerializer` : Sérialisation complète du type de tableau
- `AnneeSerializer` : Sérialisation complète de l'année avec compteur de PACs

#### ✅ `pac/serializers.py`
Mise à jour de tous les serializers PAC :
- `PacSerializer` : Ajout des champs année et type_tableau
- `PacCreateSerializer` : Ajout des champs dans la création
- `PacUpdateSerializer` : Ajout des champs dans la mise à jour
- `PacCompletSerializer` : Ajout des champs dans la vue détaillée

**Nouveaux champs exposés** :
- `annee`, `annee_valeur`, `annee_libelle`, `annee_uuid`
- `type_tableau`, `type_tableau_code`, `type_tableau_nom`, `type_tableau_uuid`

### 5. Vues API (`parametre/views.py`)

#### ✅ Endpoints pour les Années
- `GET /api/parametre/annees/` : Liste des années actives
- `GET /api/parametre/annees/all/` : Liste de toutes les années

#### ✅ Endpoints pour les Types de Tableau
- `GET /api/parametre/types-tableau/` : Liste des types actifs
- `GET /api/parametre/types-tableau/all/` : Liste de tous les types

### 6. URLs (`parametre/urls.py`)

Ajout des routes :
```python
path('annees/', views.annees_list, name='annees_list')
path('annees/all/', views.annees_all_list, name='annees_all_list')
path('types-tableau/', views.types_tableau_list, name='types_tableau_list')
path('types-tableau/all/', views.types_tableau_all_list, name='types_tableau_all_list')
```

### 7. Commandes de gestion

#### ✅ `init_annees.py` (nouveau)
Initialise automatiquement les années de 2020 à aujourd'hui + 2 ans :
```bash
python manage.py init_annees
```
**Résultat** : 8 années créées (2020-2027)

#### ✅ `init_types_tableau.py` (mis à jour)
Adapté à la nouvelle structure du modèle TypeTableau

## 🗄️ Structure de la base de données

### Table `annee`
```sql
CREATE TABLE annee (
    uuid UUID PRIMARY KEY,
    annee INTEGER UNIQUE NOT NULL,
    libelle VARCHAR(100),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Table `pac` (nouveaux champs)
```sql
ALTER TABLE pac ADD COLUMN annee_id UUID REFERENCES annee(uuid) ON DELETE SET NULL;
ALTER TABLE pac ADD COLUMN type_tableau_id UUID REFERENCES type_tableau(uuid) ON DELETE SET NULL;
```

## 📊 Données initiales

### Années créées
- 2020 à 2027 (8 années)
- Toutes actives par défaut

### Types de Tableau existants
- `INITIAL` - Tableau Initial
- `AMENDEMENT_1` - Amendement 1
- `AMENDEMENT_2` - Amendement 2

## 🔌 Utilisation de l'API

### Récupérer les années disponibles
```bash
GET /api/parametre/annees/
```
**Réponse** :
```json
{
  "success": true,
  "data": [
    {
      "uuid": "...",
      "annee": 2024,
      "libelle": "Année 2024",
      "description": "Année fiscale 2024",
      "is_active": true,
      "pacs_count": 0,
      "created_at": "2025-10-30T10:30:00Z",
      "updated_at": "2025-10-30T10:30:00Z"
    }
  ]
}
```

### Récupérer les types de tableau
```bash
GET /api/parametre/types-tableau/
```
**Réponse** :
```json
{
  "success": true,
  "data": [
    {
      "uuid": "...",
      "code": "INITIAL",
      "nom": "Tableau Initial",
      "description": "Tableau de bord de référence...",
      "is_active": true,
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

### Créer un PAC avec année et type de tableau
```bash
POST /api/pac/pacs/
```
**Corps de la requête** :
```json
{
  "processus": "uuid-du-processus",
  "libelle": "Mon PAC",
  "annee": "uuid-de-l-annee",
  "type_tableau": "uuid-du-type-tableau",
  "nature": "uuid-de-la-nature",
  "categorie": "uuid-de-la-categorie",
  "source": "uuid-de-la-source"
}
```

## ✅ Tests effectués

- ✅ Migrations appliquées avec succès
- ✅ Modèles créés et relations établies
- ✅ Admin Django fonctionnel
- ✅ Commandes de gestion exécutées
- ✅ Pas d'erreurs de linter
- ✅ Données initiales créées (8 années + 3 types de tableau)

## 📝 Notes importantes

1. **Champs optionnels** : Les champs `annee` et `type_tableau` sont **nullables** pour permettre la rétrocompatibilité avec les PAC existants.

2. **SET_NULL** : En cas de suppression d'une année ou d'un type de tableau, les PAC associés ne seront pas supprimés mais le champ sera mis à NULL.

3. **Ordre de tri** : Les années sont triées par ordre décroissant (les plus récentes en premier).

4. **Filtrage** : Les endpoints `/annees/` et `/types-tableau/` retournent uniquement les éléments actifs (`is_active=True`). Utiliser `/all/` pour obtenir tous les éléments.

## 🚀 Prochaines étapes suggérées

1. **Frontend** : Mettre à jour les formulaires de création/édition de PAC pour inclure les sélecteurs d'année et de type de tableau

2. **Filtrage** : Ajouter des filtres dans la liste des PAC pour filtrer par année et type de tableau

3. **Statistiques** : Créer des vues statistiques par année et type de tableau

4. **Validation** : Ajouter des règles métier si nécessaire (ex: une année ne peut pas être dans le futur au-delà de 2 ans)

## 📞 Support

Pour toute question ou problème, consulter :
- Les modèles : `backend/parametre/models.py` et `backend/pac/models.py`
- Les migrations : `backend/pac/migrations/` et `backend/parametre/migrations/`
- L'admin : Accessible via `/admin/`

