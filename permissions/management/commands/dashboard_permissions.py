"""
Définitions des actions de permissions pour l'application Dashboard
"""


def get_dashboard_actions():
    """Définit les actions pour l'application Dashboard"""
    return [
        {
            'code': 'create_tableau_bord',
            'nom': 'Créer un tableau de bord',
            'description': 'Permet de créer un nouveau tableau de bord',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_tableau_bord',
            'nom': 'Modifier un tableau de bord',
            'description': 'Permet de modifier un tableau de bord existant',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_tableau_bord',
            'nom': 'Supprimer un tableau de bord',
            'description': 'Permet de supprimer un tableau de bord',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'validate_tableau_bord',
            'nom': 'Valider un tableau de bord',
            'description': 'Permet de valider un tableau de bord',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'read_tableau_bord',
            'nom': 'Lire un tableau de bord',
            'description': 'Permet de consulter un tableau de bord',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': True, 'priority': 5},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'create_amendement',
            'nom': 'Créer un amendement',
            'description': 'Permet de créer un amendement pour un tableau de bord',
            'category': 'main',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'create_objective',
            'nom': 'Créer un objectif',
            'description': 'Permet de créer un objectif dans un tableau de bord',
            'category': 'objectives',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_objective',
            'nom': 'Modifier un objectif',
            'description': 'Permet de modifier un objectif',
            'category': 'objectives',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_objective',
            'nom': 'Supprimer un objectif',
            'description': 'Permet de supprimer un objectif',
            'category': 'objectives',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'create_indicateur',
            'nom': 'Créer un indicateur',
            'description': 'Permet de créer un indicateur pour un objectif',
            'category': 'indicateurs',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_indicateur',
            'nom': 'Modifier un indicateur',
            'description': 'Permet de modifier un indicateur',
            'category': 'indicateurs',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }   
        },
        {
            'code': 'delete_indicateur',
            'nom': 'Supprimer un indicateur',
            'description': 'Permet de supprimer un indicateur',
            'category': 'indicateurs',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'create_cible',
            'nom': 'Créer une cible',
            'description': 'Permet de créer une cible pour un indicateur',
            'category': 'cibles',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_cible',
            'nom': 'Modifier une cible',
            'description': 'Permet de modifier une cible',
            'category': 'cibles',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_cible',
            'nom': 'Supprimer une cible',
            'description': 'Permet de supprimer une cible',
            'category': 'cibles',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'create_periodicite',
            'nom': 'Créer une périodicité',
            'description': 'Permet de créer une périodicité pour un indicateur',
            'category': 'periodicites',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_periodicite',
            'nom': 'Modifier une périodicité',
            'description': 'Permet de modifier une périodicité',
            'category': 'periodicites',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_periodicite',
            'nom': 'Supprimer une périodicité',
            'description': 'Permet de supprimer une périodicité',
            'category': 'periodicites',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
        {
            'code': 'update_frequence',
            'nom': 'Modifier la fréquence',
            'description': 'Permet de modifier la fréquence d\'un indicateur',
            'category': 'frequences',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
                'responsable_processus': {'granted': True, 'priority': 12},
            }
        },
        {
            'code': 'create_observation',
            'nom': 'Créer une observation',
            'description': 'Permet de créer une observation pour un objectif',
            'category': 'observations',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'update_observation',
            'nom': 'Modifier une observation',
            'description': 'Permet de modifier une observation',
            'category': 'observations',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'contributeur': {'granted': True, 'priority': 5, 'conditions': {'can_edit_when_validated': True}},
                'lecteur': {'granted': False, 'priority': 0},
                'admin': {'granted': True, 'priority': 8},
            }
        },
        {
            'code': 'delete_observation',
            'nom': 'Supprimer une observation',
            'description': 'Permet de supprimer une observation',
            'category': 'observations',
            'role_mappings': {
                'validateur': {'granted': True, 'priority': 10},
                'admin': {'granted': True, 'priority': 8},
                'contributeur': {'granted': False, 'priority': 0},
                'lecteur': {'granted': False, 'priority': 0},
            }
        },
    ]

