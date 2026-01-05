"""
Définitions des actions de permissions pour l'application PAC (Plan d'Action de Conformité)
"""


def get_pac_actions():
    """Définit les actions pour l'application PAC"""
    return [
        {
            'code': 'create_pac',
            'nom': 'Créer un Plan d\'Action de Conformité',
            'description': 'Permet de créer un nouveau PAC',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_pac',
            'nom': 'Modifier un Plan d\'Action de Conformité',
            'description': 'Permet de modifier un PAC existant',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_pac',
            'nom': 'Supprimer un Plan d\'Action de Conformité',
            'description': 'Permet de supprimer un PAC',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'validate_pac',
            'nom': 'Valider un Plan d\'Action de Conformité',
            'description': 'Permet de valider un PAC pour permettre la création des suivis',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'read_pac',
            'nom': 'Lire un Plan d\'Action de Conformité',
            'description': 'Permet de consulter un PAC',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': True, 'priority': 5},
            }
        },
        {
            'code': 'unvalidate_pac',
            'nom': 'Dévalider un Plan d\'Action de Conformité',
            'description': 'Permet de dévalider un PAC pour permettre les modifications',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'create_amendement_pac',
            'nom': 'Créer un amendement PAC',
            'description': 'Permet de créer un amendement pour un Plan d\'Action de Conformité',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'create_detail_pac',
            'nom': 'Créer un détail PAC',
            'description': 'Permet de créer un détail dans un PAC',
            'category': 'details',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_detail_pac',
            'nom': 'Modifier un détail PAC',
            'description': 'Permet de modifier un détail PAC',
            'category': 'details',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_detail_pac',
            'nom': 'Supprimer un détail PAC',
            'description': 'Permet de supprimer un détail PAC',
            'category': 'details',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'create_traitement',
            'nom': 'Créer un traitement',
            'description': 'Permet de créer un traitement pour un détail PAC',
            'category': 'traitements',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_traitement',
            'nom': 'Modifier un traitement',
            'description': 'Permet de modifier un traitement',
            'category': 'traitements',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_traitement',
            'nom': 'Supprimer un traitement',
            'description': 'Permet de supprimer un traitement',
            'category': 'traitements',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'create_suivi',
            'nom': 'Créer un suivi',
            'description': 'Permet de créer un suivi pour un traitement',
            'category': 'suivis',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_suivi',
            'nom': 'Modifier un suivi',
            'description': 'Permet de modifier un suivi',
            'category': 'suivis',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_suivi',
            'nom': 'Supprimer un suivi',
            'description': 'Permet de supprimer un suivi',
            'category': 'suivis',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
    ]

