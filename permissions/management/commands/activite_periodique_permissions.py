"""
Définitions des actions de permissions pour l'application Activité Périodique

Roles :
  admin                   — creation, suppression, validation, devalidation, amendement
  RESPONSABLE DE PROCESSUS — lecture + modification + suppression des sous-elements
  PILOTE DE PROCESSUS      — lecture + modification des sous-elements (update_activite_periodique refusé)
  CO-PILOTE DE APROCESSUS  — lecture seule
  superviseur_smi          — tout (géré par seed_superviseur_smi_permissions)
"""

RP = 'RESPONSABLE DE PROCESSUS'
PP = 'PILOTE DE PROCESSUS'
CP = 'CO-PILOTE DE APROCESSUS'


def get_activite_periodique_actions():
    """Définit les actions pour l'application Activité Périodique"""
    return [
        # ==================== ENTITE PRINCIPALE ====================
        {
            'code': 'create_activite_periodique',
            'nom': 'Créer une Activité Périodique',
            'description': 'Permet de créer une nouvelle Activité Périodique',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_activite_periodique',
            'nom': 'Modifier une Activité Périodique',
            'description': 'Permet de modifier une Activité Périodique existante',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'delete_activite_periodique',
            'nom': 'Supprimer une Activité Périodique',
            'description': 'Permet de supprimer une Activité Périodique',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'validate_activite_periodique',
            'nom': 'Valider une Activité Périodique',
            'description': 'Permet de valider une Activité Périodique pour permettre la création des suivis',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'read_activite_periodique',
            'nom': 'Lire une Activité Périodique',
            'description': 'Permet de consulter une Activité Périodique',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': True, 'priority': 0},
                CP: {'granted': True, 'priority': 0},
            }
        },
        {
            'code': 'unvalidate_activite_periodique',
            'nom': 'Dévalider une Activité Périodique',
            'description': 'Permet de dévalider une Activité Périodique pour permettre les modifications',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'create_amendement_activite_periodique',
            'nom': 'Créer un amendement d\'Activité Périodique',
            'description': 'Permet de créer un amendement pour une Activité Périodique',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        # ==================== DETAILS ====================
        {
            'code': 'create_detail_activite_periodique',
            'nom': 'Créer un détail d\'Activité Périodique',
            'description': 'Permet de créer un détail pour une Activité Périodique',
            'category': 'details',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_detail_activite_periodique',
            'nom': 'Modifier un détail d\'Activité Périodique',
            'description': 'Permet de modifier un détail d\'Activité Périodique',
            'category': 'details',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': True, 'priority': 0},
            }
        },
        {
            'code': 'delete_detail_activite_periodique',
            'nom': 'Supprimer un détail d\'Activité Périodique',
            'description': 'Permet de supprimer un détail d\'Activité Périodique',
            'category': 'details',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
            }
        },
        # ==================== SUIVIS ====================
        {
            'code': 'create_suivi_activite_periodique',
            'nom': 'Créer un suivi d\'Activité Périodique',
            'description': 'Permet de créer un suivi pour une Activité Périodique',
            'category': 'suivis',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_suivi_activite_periodique',
            'nom': 'Modifier un suivi d\'Activité Périodique',
            'description': 'Permet de modifier un suivi d\'Activité Périodique',
            'category': 'suivis',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': True, 'priority': 0},
            }
        },
        {
            'code': 'delete_suivi_activite_periodique',
            'nom': 'Supprimer un suivi d\'Activité Périodique',
            'description': 'Permet de supprimer un suivi d\'Activité Périodique',
            'category': 'suivis',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
            }
        },
    ]
