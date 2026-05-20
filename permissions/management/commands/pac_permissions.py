"""
Définitions des actions de permissions pour l'application PAC (Plan d'Action de Conformité)

Roles :
  admin                   — creation, suppression, validation, devalidation, amendement
  RESPONSABLE DE PROCESSUS — lecture + modification + suppression sous-elements
  PILOTE DE PROCESSUS      — lecture + modification sous-elements (sans suppression)
  CO-PILOTE DE APROCESSUS  — lecture seule
  superviseur_smi          — tout (géré par seed_superviseur_smi_permissions)
"""

RP = 'RESPONSABLE DE PROCESSUS'
PP = 'PILOTE DE PROCESSUS'
CP = 'CO-PILOTE DE APROCESSUS'


def get_pac_actions():
    """Définit les actions pour l'application PAC"""
    return [
        # ==================== ENTITE PRINCIPALE ====================
        {
            'code': 'create_pac',
            'nom': 'Créer un Plan d\'Action de Conformité',
            'description': 'Permet de créer un nouveau PAC',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_pac',
            'nom': 'Modifier un Plan d\'Action de Conformité',
            'description': 'Permet de modifier un PAC existant',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': True, 'priority': 0},
            }
        },
        {
            'code': 'delete_pac',
            'nom': 'Supprimer un Plan d\'Action de Conformité',
            'description': 'Permet de supprimer un PAC',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'validate_pac',
            'nom': 'Valider un Plan d\'Action de Conformité',
            'description': 'Permet de valider un PAC pour permettre la création des suivis',
            'category': 'main',
            'role_mappings': {
                # Seul le superviseur_smi peut valider (via seed_superviseur_smi_permissions)
            }
        },
        {
            'code': 'read_pac',
            'nom': 'Lire un Plan d\'Action de Conformité',
            'description': 'Permet de consulter un PAC',
            'category': 'main',
            'role_mappings': {
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': True, 'priority': 0},
                CP: {'granted': True, 'priority': 0},
            }
        },
        {
            'code': 'unvalidate_pac',
            'nom': 'Dévalider un Plan d\'Action de Conformité',
            'description': 'Permet de dévalider un PAC pour permettre les modifications',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'create_amendement_pac',
            'nom': 'Créer un amendement PAC',
            'description': 'Permet de créer un amendement pour un Plan d\'Action de Conformité',
            'category': 'main',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        # ==================== DETAILS ====================
        {
            'code': 'create_detail_pac',
            'nom': 'Créer un détail PAC',
            'description': 'Permet de créer un détail dans un PAC',
            'category': 'details',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_detail_pac',
            'nom': 'Modifier un détail PAC',
            'description': 'Permet de modifier un détail PAC',
            'category': 'details',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': True, 'priority': 0},
            }
        },
        {
            'code': 'delete_detail_pac',
            'nom': 'Supprimer un détail PAC',
            'description': 'Permet de supprimer un détail PAC',
            'category': 'details',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
            }
        },
        # ==================== TRAITEMENTS ====================
        {
            'code': 'create_traitement',
            'nom': 'Créer un traitement',
            'description': 'Permet de créer un traitement pour un détail PAC',
            'category': 'traitements',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_traitement',
            'nom': 'Modifier un traitement',
            'description': 'Permet de modifier un traitement',
            'category': 'traitements',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': True, 'priority': 0},
            }
        },
        {
            'code': 'delete_traitement',
            'nom': 'Supprimer un traitement',
            'description': 'Permet de supprimer un traitement',
            'category': 'traitements',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
            }
        },
        # ==================== SUIVIS ====================
        {
            'code': 'create_suivi',
            'nom': 'Créer un suivi',
            'description': 'Permet de créer un suivi pour un traitement',
            'category': 'suivis',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_suivi',
            'nom': 'Modifier un suivi',
            'description': 'Permet de modifier un suivi',
            'category': 'suivis',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
                PP: {'granted': True, 'priority': 0},
            }
        },
        {
            'code': 'delete_suivi',
            'nom': 'Supprimer un suivi',
            'description': 'Permet de supprimer un suivi',
            'category': 'suivis',
            'role_mappings': {
                'admin': {'granted': True, 'priority': 8},
                RP: {'granted': True, 'priority': 0},
            }
        },
    ]
