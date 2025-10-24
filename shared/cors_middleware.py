"""
Middleware pour corriger le Content-Type des requêtes CORS
"""
import logging

logger = logging.getLogger(__name__)


class CORSContentTypeMiddleware:
    """
    Middleware pour corriger le Content-Type des requêtes CORS
    Safari et certains navigateurs changent le Content-Type en text/plain
    pour les requêtes CORS simples
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Si c'est une requête POST/PUT/PATCH vers l'API
        if request.method in ['POST', 'PUT', 'PATCH'] and request.path.startswith('/api/'):
            # Et que le Content-Type est text/plain
            if request.content_type == 'text/plain':
                # Forcer le Content-Type à application/json
                request.META['CONTENT_TYPE'] = 'application/json'
        
        response = self.get_response(request)
        return response

