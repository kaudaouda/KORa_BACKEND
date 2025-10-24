"""
Parsers personnalisés pour Django REST Framework
"""
from rest_framework.parsers import JSONParser
import logging

logger = logging.getLogger(__name__)


class PlainTextAsJSONParser(JSONParser):
    """
    Parser qui traite text/plain comme du JSON
    Utilisé pour les requêtes CORS de Safari qui envoient text/plain au lieu de application/json
    """
    media_type = 'text/plain'
    
    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parse le stream comme du JSON même si le Content-Type est text/plain
        """
        # Appeler le parser JSON parent
        return super().parse(stream, media_type='application/json', parser_context=parser_context)

