"""
Gestion centralisée des chemins de stockage des fichiers (Media.fichier).

Objectif : ranger les fichiers uploadés dans des sous-dossiers par app
au lieu de tout mettre à plat dans MEDIA_ROOT.

Le modèle `Media` (parametre.models.Media) est partagé entre plusieurs apps.
Au moment de la création d'une instance, la view qui upload le fichier peut
définir un attribut temporaire `instance._app_folder` (str) pour indiquer
à quelle app appartient le fichier. Si l'attribut n'est pas défini, le
fichier est rangé dans `shared/` (fallback sûr).

Sous-dossiers connus (doivent exister dans MEDIA_ROOT) :
    - pac/
    - dashboard/
    - cartographie_risque/
    - activite_periodique/
    - documentation/
    - parametre/
    - shared/   (fallback)
"""

# Liste des sous-dossiers autorisés (whitelist) pour éviter qu'une valeur
# arbitraire envoyée par le frontend pollue l'arborescence MEDIA_ROOT.
ALLOWED_APP_FOLDERS = {
    'pac',
    'dashboard',
    'cartographie_risque',
    'activite_periodique',
    'documentation',
    'parametre',
    'shared',
}

DEFAULT_APP_FOLDER = 'shared'


def normalize_app_folder(value):
    """
    Normalise et valide un nom de sous-dossier app.
    Retourne DEFAULT_APP_FOLDER si la valeur est invalide ou absente.
    """
    if not value:
        return DEFAULT_APP_FOLDER
    value = str(value).strip().lower()
    # Alias courants
    aliases = {
        'cdr': 'cartographie_risque',
        'risque': 'cartographie_risque',
        'ap': 'activite_periodique',
        'doc': 'documentation',
        'docs': 'documentation',
    }
    value = aliases.get(value, value)
    if value in ALLOWED_APP_FOLDERS:
        return value
    return DEFAULT_APP_FOLDER


def media_upload_path(instance, filename):
    """
    Callable utilisé par `Media.fichier.upload_to`.

    Lit l'attribut temporaire `instance._app_folder` posé par la view
    avant le `save()`. Fallback sur `shared/` si non défini.
    """
    folder = normalize_app_folder(getattr(instance, '_app_folder', None))
    return f'{folder}/{filename}'
