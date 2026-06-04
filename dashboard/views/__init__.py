"""Auto-generated exports — do not edit manually."""
from .tableaux import tableaux_bord_list_create, tableau_bord_detail, create_amendement, get_amendements_by_initial, validate_tableau_bord, devalidate_tableau_bord, tableau_bord_objectives
from .objectives import objectives_list, objectives_detail, objectives_create, objectives_update, objectives_delete
from .stats import dashboard_stats
from .indicateurs import indicateurs_list, indicateurs_detail, indicateurs_create, indicateurs_update, indicateurs_delete, objectives_indicateurs
from .cibles import cibles_list, cibles_detail, cibles_create, cibles_update, cibles_delete, cibles_by_indicateur
from .periodicites import periodicites_list, periodicites_detail, periodicites_create, periodicites_update, periodicites_delete, periodicites_by_indicateur
from .observations import observations_list, observations_create, observations_detail, observations_update, observations_delete, observations_by_indicateur, get_last_tableau_bord_previous_year
