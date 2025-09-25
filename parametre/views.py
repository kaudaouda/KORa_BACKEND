"""
Vues API pour l'application Paramètre
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from .models import (
    Nature, Categorie, Source, ActionType, Statut, 
    EtatMiseEnOeuvre, Appreciation, Direction, SousDirection
)
import logging

logger = logging.getLogger(__name__)


# ==================== SERIALIZERS SIMPLES ====================

def serialize_nature(nature):
    return {
        'uuid': str(nature.uuid),
        'nom': nature.nom,
        'description': nature.description,
        'created_at': nature.created_at.isoformat(),
        'updated_at': nature.updated_at.isoformat()
    }

def serialize_categorie(categorie):
    return {
        'uuid': str(categorie.uuid),
        'nom': categorie.nom,
        'description': categorie.description,
        'created_at': categorie.created_at.isoformat(),
        'updated_at': categorie.updated_at.isoformat()
    }

def serialize_source(source):
    return {
        'uuid': str(source.uuid),
        'nom': source.nom,
        'description': source.description,
        'created_at': source.created_at.isoformat(),
        'updated_at': source.updated_at.isoformat()
    }

def serialize_action_type(action_type):
    return {
        'uuid': str(action_type.uuid),
        'nom': action_type.nom,
        'description': action_type.description,
        'created_at': action_type.created_at.isoformat(),
        'updated_at': action_type.updated_at.isoformat()
    }

def serialize_statut(statut):
    return {
        'uuid': str(statut.uuid),
        'nom': statut.nom,
        'description': statut.description,
        'created_at': statut.created_at.isoformat(),
        'updated_at': statut.updated_at.isoformat()
    }

def serialize_etat_mise_en_oeuvre(etat):
    return {
        'uuid': str(etat.uuid),
        'nom': etat.nom,
        'description': etat.description,
        'created_at': etat.created_at.isoformat(),
        'updated_at': etat.updated_at.isoformat()
    }

def serialize_appreciation(appreciation):
    return {
        'uuid': str(appreciation.uuid),
        'nom': appreciation.nom,
        'description': appreciation.description,
        'created_at': appreciation.created_at.isoformat(),
        'updated_at': appreciation.updated_at.isoformat()
    }

def serialize_direction(direction):
    return {
        'uuid': str(direction.uuid),
        'nom': direction.nom,
        'description': direction.description,
        'created_at': direction.created_at.isoformat(),
        'updated_at': direction.updated_at.isoformat()
    }

def serialize_sous_direction(sous_direction):
    return {
        'uuid': str(sous_direction.uuid),
        'nom': sous_direction.nom,
        'description': sous_direction.description,
        'direction': str(sous_direction.direction.uuid),
        'created_at': sous_direction.created_at.isoformat(),
        'updated_at': sous_direction.updated_at.isoformat()
    }


# ==================== NATURES ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def nature_list(request):
    """Liste des natures"""
    try:
        natures = Nature.objects.all().order_by('nom')
        data = [serialize_nature(nature) for nature in natures]
        return Response(data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des natures: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les natures'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def nature_create(request):
    """Créer une nouvelle nature"""
    try:
        nom = request.data.get('nom')
        description = request.data.get('description', '')
        
        if not nom:
            return Response({
                'error': 'Le nom est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si une nature avec ce nom existe déjà
        nature, created = Nature.objects.get_or_create(
            nom=nom,
            defaults={'description': description}
        )
        
        if created:
            return Response(serialize_nature(nature), status=status.HTTP_201_CREATED)
        else:
            return Response(serialize_nature(nature), status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la nature: {str(e)}")
        return Response({
            'error': 'Impossible de créer la nature'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def nature_detail(request, uuid):
    """Détails d'une nature"""
    try:
        nature = Nature.objects.get(uuid=uuid)
        return Response(serialize_nature(nature))
    except Nature.DoesNotExist:
        return Response({
            'error': 'Nature non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la nature: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer la nature'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)# Ajouter ce contenu à la fin du fichier views.py

# ==================== CATÉGORIES ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def categorie_list(request):
    """Liste des catégories"""
    try:
        categories = Categorie.objects.all().order_by('nom')
        data = [serialize_categorie(categorie) for categorie in categories]
        return Response(data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des catégories: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les catégories'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def categorie_create(request):
    """Créer une nouvelle catégorie"""
    try:
        nom = request.data.get('nom')
        description = request.data.get('description', '')
        
        if not nom:
            return Response({
                'error': 'Le nom est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si une catégorie avec ce nom existe déjà
        categorie, created = Categorie.objects.get_or_create(
            nom=nom,
            defaults={'description': description}
        )
        
        if created:
            return Response(serialize_categorie(categorie), status=status.HTTP_201_CREATED)
        else:
            return Response(serialize_categorie(categorie), status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la catégorie: {str(e)}")
        return Response({
            'error': 'Impossible de créer la catégorie'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def categorie_detail(request, uuid):
    """Détails d'une catégorie"""
    try:
        categorie = Categorie.objects.get(uuid=uuid)
        return Response(serialize_categorie(categorie))
    except Categorie.DoesNotExist:
        return Response({
            'error': 'Catégorie non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la catégorie: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer la catégorie'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== SOURCES ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def source_list(request):
    """Liste des sources"""
    try:
        sources = Source.objects.all().order_by('nom')
        data = [serialize_source(source) for source in sources]
        return Response(data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sources: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les sources'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def source_create(request):
    """Créer une nouvelle source"""
    try:
        nom = request.data.get('nom')
        description = request.data.get('description', '')
        
        if not nom:
            return Response({
                'error': 'Le nom est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si une source avec ce nom existe déjà
        source, created = Source.objects.get_or_create(
            nom=nom,
            defaults={'description': description}
        )
        
        if created:
            return Response(serialize_source(source), status=status.HTTP_201_CREATED)
        else:
            return Response(serialize_source(source), status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la source: {str(e)}")
        return Response({
            'error': 'Impossible de créer la source'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def source_detail(request, uuid):
    """Détails d'une source"""
    try:
        source = Source.objects.get(uuid=uuid)
        return Response(serialize_source(source))
    except Source.DoesNotExist:
        return Response({
            'error': 'Source non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la source: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer la source'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== TYPES D'ACTION ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def action_type_list(request):
    """Liste des types d'action"""
    try:
        action_types = ActionType.objects.all().order_by('nom')
        data = [serialize_action_type(action_type) for action_type in action_types]
        return Response(data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des types d'action: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les types d\'action'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def action_type_create(request):
    """Créer un nouveau type d'action"""
    try:
        nom = request.data.get('nom')
        description = request.data.get('description', '')
        
        if not nom:
            return Response({
                'error': 'Le nom est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si un type d'action avec ce nom existe déjà
        action_type, created = ActionType.objects.get_or_create(
            nom=nom,
            defaults={'description': description}
        )
        
        if created:
            return Response(serialize_action_type(action_type), status=status.HTTP_201_CREATED)
        else:
            return Response(serialize_action_type(action_type), status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création du type d'action: {str(e)}")
        return Response({
            'error': 'Impossible de créer le type d\'action'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def action_type_detail(request, uuid):
    """Détails d'un type d'action"""
    try:
        action_type = ActionType.objects.get(uuid=uuid)
        return Response(serialize_action_type(action_type))
    except ActionType.DoesNotExist:
        return Response({
            'error': 'Type d\'action non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du type d'action: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le type d\'action'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== STATUTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def statut_list(request):
    """Liste des statuts"""
    try:
        statuts = Statut.objects.all().order_by('nom')
        data = [serialize_statut(statut) for statut in statuts]
        return Response(data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statuts: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les statuts'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def statut_create(request):
    """Créer un nouveau statut"""
    try:
        nom = request.data.get('nom')
        description = request.data.get('description', '')
        
        if not nom:
            return Response({
                'error': 'Le nom est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si un statut avec ce nom existe déjà
        statut, created = Statut.objects.get_or_create(
            nom=nom,
            defaults={'description': description}
        )
        
        if created:
            return Response(serialize_statut(statut), status=status.HTTP_201_CREATED)
        else:
            return Response(serialize_statut(statut), status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création du statut: {str(e)}")
        return Response({
            'error': 'Impossible de créer le statut'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def statut_detail(request, uuid):
    """Détails d'un statut"""
    try:
        statut = Statut.objects.get(uuid=uuid)
        return Response(serialize_statut(statut))
    except Statut.DoesNotExist:
        return Response({
            'error': 'Statut non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du statut: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer le statut'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== ÉTATS DE MISE EN ŒUVRE ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def etat_mise_en_oeuvre_list(request):
    """Liste des états de mise en œuvre"""
    try:
        etats = EtatMiseEnOeuvre.objects.all().order_by('nom')
        data = [serialize_etat_mise_en_oeuvre(etat) for etat in etats]
        return Response(data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des états de mise en œuvre: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les états de mise en œuvre'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def etat_mise_en_oeuvre_create(request):
    """Créer un nouvel état de mise en œuvre"""
    try:
        nom = request.data.get('nom')
        description = request.data.get('description', '')
        
        if not nom:
            return Response({
                'error': 'Le nom est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si un état avec ce nom existe déjà
        etat, created = EtatMiseEnOeuvre.objects.get_or_create(
            nom=nom,
            defaults={'description': description}
        )
        
        if created:
            return Response(serialize_etat_mise_en_oeuvre(etat), status=status.HTTP_201_CREATED)
        else:
            return Response(serialize_etat_mise_en_oeuvre(etat), status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'état de mise en œuvre: {str(e)}")
        return Response({
            'error': 'Impossible de créer l\'état de mise en œuvre'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def etat_mise_en_oeuvre_detail(request, uuid):
    """Détails d'un état de mise en œuvre"""
    try:
        etat = EtatMiseEnOeuvre.objects.get(uuid=uuid)
        return Response(serialize_etat_mise_en_oeuvre(etat))
    except EtatMiseEnOeuvre.DoesNotExist:
        return Response({
            'error': 'État de mise en œuvre non trouvé'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'état de mise en œuvre: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer l\'état de mise en œuvre'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== APPRÉCIATIONS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def appreciation_list(request):
    """Liste des appréciations"""
    try:
        appreciations = Appreciation.objects.all().order_by('nom')
        data = [serialize_appreciation(appreciation) for appreciation in appreciations]
        return Response(data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des appréciations: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les appréciations'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def appreciation_create(request):
    """Créer une nouvelle appréciation"""
    try:
        nom = request.data.get('nom')
        description = request.data.get('description', '')
        
        if not nom:
            return Response({
                'error': 'Le nom est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si une appréciation avec ce nom existe déjà
        appreciation, created = Appreciation.objects.get_or_create(
            nom=nom,
            defaults={'description': description}
        )
        
        if created:
            return Response(serialize_appreciation(appreciation), status=status.HTTP_201_CREATED)
        else:
            return Response(serialize_appreciation(appreciation), status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'appréciation: {str(e)}")
        return Response({
            'error': 'Impossible de créer l\'appréciation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def appreciation_detail(request, uuid):
    """Détails d'une appréciation"""
    try:
        appreciation = Appreciation.objects.get(uuid=uuid)
        return Response(serialize_appreciation(appreciation))
    except Appreciation.DoesNotExist:
        return Response({
            'error': 'Appréciation non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de l'appréciation: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer l\'appréciation'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ==================== DIRECTIONS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def direction_list(request):
    """Liste des directions"""
    try:
        directions = Direction.objects.all().order_by('nom')
        data = [serialize_direction(direction) for direction in directions]
        return Response(data)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des directions: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les directions'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def direction_create(request):
    """Créer une nouvelle direction"""
    try:
        nom = request.data.get('nom')
        description = request.data.get('description', '')
        
        if not nom:
            return Response({
                'error': 'Le nom est requis'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Vérifier si une direction avec ce nom existe déjà
        direction, created = Direction.objects.get_or_create(
            nom=nom,
            defaults={'description': description}
        )
        
        if created:
            return Response(serialize_direction(direction), status=status.HTTP_201_CREATED)
        else:
            return Response(serialize_direction(direction), status=status.HTTP_200_OK)
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de la direction: {str(e)}")
        return Response({
            'error': 'Impossible de créer la direction'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def direction_detail(request, uuid):
    """Détails d'une direction"""
    try:
        direction = Direction.objects.get(uuid=uuid)
        return Response(serialize_direction(direction))
    except Direction.DoesNotExist:
        return Response({
            'error': 'Direction non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la direction: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer la direction'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def sous_direction_list(request, uuid):
    """Liste des sous-directions d'une direction"""
    try:
        direction = Direction.objects.get(uuid=uuid)
        sous_directions = SousDirection.objects.filter(direction=direction).order_by('nom')
        data = [serialize_sous_direction(sous_direction) for sous_direction in sous_directions]
        return Response(data)
    except Direction.DoesNotExist:
        return Response({
            'error': 'Direction non trouvée'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des sous-directions: {str(e)}")
        return Response({
            'error': 'Impossible de récupérer les sous-directions'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
