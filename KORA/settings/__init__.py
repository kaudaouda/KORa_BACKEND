import os

_env = os.getenv('DJANGO_ENV', 'development').lower()

if _env == 'production':
    from .prod import *
else:
    from .dev import *
