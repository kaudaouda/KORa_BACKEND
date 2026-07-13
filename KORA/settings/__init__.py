import os
from pathlib import Path
from dotenv import load_dotenv

# Charger le .env AVANT de lire DJANGO_ENV, sinon os.getenv renvoie toujours
# la valeur par défaut 'development' et prod.py n'est jamais importé.
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env')

_env = os.getenv('DJANGO_ENV', 'development').lower()

if _env == 'production':
    from .prod import *
else:
    from .dev import *
