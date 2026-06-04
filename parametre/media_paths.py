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

import os
import uuid as uuid_lib

# ── Whitelist sous-dossiers ────────────────────────────────────────────────────

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

# ── Validation des fichiers uploadés ──────────────────────────────────────────

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 Mo

ALLOWED_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.jpg', '.jpeg', '.png', '.gif', '.txt', '.csv', '.zip',
}

ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'image/jpeg',
    'image/png',
    'image/gif',
    'text/plain',
    'text/csv',
    'application/zip',
    'application/x-zip-compressed',
    'application/octet-stream',
}

# Magic bytes attendus par extension (8 premiers octets suffisent).
# Les formats texte (.txt, .csv) n'ont pas de signature binaire fiable.
_EXT_MAGIC = {
    '.pdf':  [b'%PDF'],
    '.jpg':  [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.png':  [b'\x89PNG\r\n\x1a\n'],
    '.gif':  [b'GIF87a', b'GIF89a'],
    # Formats Office modernes (.docx/.xlsx/.pptx) et .zip partagent la signature ZIP
    '.docx': [b'PK\x03\x04'],
    '.xlsx': [b'PK\x03\x04'],
    '.pptx': [b'PK\x03\x04'],
    '.zip':  [b'PK\x03\x04'],
    # Formats Office legacy (OLE2 Compound Document)
    '.doc':  [b'\xd0\xcf\x11\xe0'],
    '.xls':  [b'\xd0\xcf\x11\xe0'],
    '.ppt':  [b'\xd0\xcf\x11\xe0'],
}


def validate_uploaded_file(fichier):
    """
    Valide un fichier uploadé : taille, extension, type MIME et magic bytes.
    Retourne un message d'erreur (str) ou None si le fichier est valide.
    """
    if fichier.size > MAX_UPLOAD_SIZE:
        max_mb = MAX_UPLOAD_SIZE // (1024 * 1024)
        return f'Le fichier dépasse la taille maximale autorisée ({max_mb} Mo).'

    ext = os.path.splitext(fichier.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        return f'Extension non autorisée. Extensions acceptées : {allowed}'

    content_type = getattr(fichier, 'content_type', '') or ''
    content_type = content_type.split(';')[0].strip().lower()
    if not content_type or content_type not in ALLOWED_MIME_TYPES:
        return f'Type de fichier non autorisé ({content_type}).'

    # Vérification des magic bytes : le contenu doit correspondre à l'extension déclarée.
    expected_signatures = _EXT_MAGIC.get(ext)
    if expected_signatures:
        try:
            header = fichier.read(8)
            fichier.seek(0)
            if not any(header.startswith(sig) for sig in expected_signatures):
                return f'Le contenu du fichier ne correspond pas à son extension ({ext}).'
        except (IOError, OSError):
            return 'Impossible de lire le fichier pour vérification.'

    return None


# ── Chemins de stockage ────────────────────────────────────────────────────────

def normalize_app_folder(value):
    """
    Normalise et valide un nom de sous-dossier app.
    Retourne DEFAULT_APP_FOLDER si la valeur est invalide ou absente.
    """
    if not value:
        return DEFAULT_APP_FOLDER
    value = str(value).strip().lower()
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

    Renomme le fichier avec un UUID pour éviter les collisions et les chemins
    prédictibles. L'extension originale est conservée.
    """
    folder = normalize_app_folder(getattr(instance, '_app_folder', None))
    ext = os.path.splitext(filename)[1].lower()
    new_filename = f"{uuid_lib.uuid4().hex}{ext}"
    return f'{folder}/{new_filename}'
