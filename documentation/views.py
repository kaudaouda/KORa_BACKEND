"""
Vues API pour l'application Documentation
"""
import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from .models import Document
from .serializers import (
    DocumentSerializer,
    DocumentCreateSerializer,
    DocumentUpdateSerializer,
    DocumentAmendSerializer
)
from parametre.models import EditionDocument, AmendementDocument, TypeDocument, Media, MediaDocument  # Pour editions_list, amendements_list et types_document_list
from parametre.views import (
    log_document_creation,
    log_document_update,
    get_client_ip
)

logger = logging.getLogger(__name__)


def validate_pdf_file(fichier):
    """
    Valide qu'un fichier est un PDF
    """
    if not fichier:
        return True  # Pas de fichier = pas d'erreur

    # Vérifier l'extension du fichier
    if not fichier.name.lower().endswith('.pdf'):
        raise ValidationError('Seuls les fichiers PDF sont acceptés')

    # Vérifier le type MIME
    content_type = fichier.content_type
    if content_type and content_type != 'application/pdf':
        raise ValidationError('Le fichier doit être au format PDF')

    # Vérifier la taille (10MB max)
    max_size = 10 * 1024 * 1024  # 10MB
    if fichier.size > max_size:
        raise ValidationError('La taille du fichier ne doit pas dépasser 10MB')

    return True


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_list(request):
    """
    Récupérer la liste des documents
    Par défaut, retourne uniquement les documents ACTIFS
    Paramètres query:
        - show_all=true : pour afficher tous les documents (actifs + inactifs)
        - is_active=true/false : pour filtrer par statut actif
        - latest_only=true : pour afficher uniquement les derniers amendements (sans les versions précédentes)
    """
    try:
        # Par défaut, filtrer sur les documents actifs
        show_all = request.GET.get('show_all', 'false').lower() == 'true'
        is_active = request.GET.get('is_active', None)
        latest_only = request.GET.get('latest_only', 'false').lower() == 'true'

        if show_all:
            # Afficher tous les documents (actifs + inactifs)
            documents = Document.objects.all().order_by('-created_at')
        elif is_active is not None:
            # Filtrer par statut actif spécifique
            is_active_bool = is_active.lower() == 'true'
            documents = Document.objects.filter(is_active=is_active_bool).order_by('-created_at')
        else:
            # Par défaut : uniquement les documents actifs
            documents = Document.objects.filter(is_active=True).order_by('-created_at')

        # Si latest_only=true, filtrer pour n'afficher que les derniers amendements
        if latest_only:
            # Exclure tous les documents qui ont des amendements (ne garder que les feuilles)
            # Un document est "latest" s'il n'a pas d'amendements
            documents = documents.filter(amendments__isnull=True)

        serializer = DocumentSerializer(documents, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_list_active(request):
    """
    Récupérer la liste des documents actifs uniquement
    """
    try:
        documents = Document.objects.filter(is_active=True).order_by('-created_at')
        serializer = DocumentSerializer(documents, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_detail(request, uuid):
    """
    Récupérer les détails d'un document
    """
    try:
        document = get_object_or_404(Document, uuid=uuid)
        serializer = DocumentSerializer(document, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_create(request):
    """
    Créer un nouveau document
    Le serializer gère automatiquement Edition 1 et Amendement 0 par défaut
    Si un fichier est fourni, il sera uploadé et associé au document
    """
    try:
        # Récupérer le fichier s'il est présent
        fichier = request.FILES.get('document_file')

        # Valider le fichier PDF
        try:
            validate_pdf_file(fichier)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Créer le document avec les données du formulaire
        serializer = DocumentCreateSerializer(data=request.data)
        if serializer.is_valid():
            document = serializer.save()

            # Si un fichier est fourni, créer le média et la relation
            if fichier:
                try:
                    # Créer le média
                    media = Media.objects.create(
                        fichier=fichier,
                        description=f'Fichier du document: {document.name}'
                    )

                    # Créer la relation MediaDocument
                    MediaDocument.objects.create(
                        document=document,
                        media=media
                    )
                except Exception as media_error:
                    # Si l'upload du média échoue, on continue quand même
                    # Le document est créé mais sans média
                    logger.error(f"Erreur lors de la création du média pour le document {document.uuid}: {str(media_error)}")

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_document_creation(request.user, document, ip_address, user_agent)
            except Exception as log_error:
                logger.error(f"Erreur lors du logging de la création du document: {log_error}")

            response_serializer = DocumentSerializer(document, context={'request': request})
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def document_update(request, uuid):
    """
    Mettre à jour un document
    """
    try:
        document = get_object_or_404(Document, uuid=uuid)
        serializer = DocumentUpdateSerializer(
            document,
            data=request.data,
            partial=(request.method == 'PATCH')
        )
        if serializer.is_valid():
            document = serializer.save()

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_document_update(request.user, document, ip_address, user_agent)
            except Exception as log_error:
                logger.error(f"Erreur lors du logging de la mise à jour du document: {log_error}")

            response_serializer = DocumentSerializer(document, context={'request': request})
            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK
            )
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def document_delete(request, uuid):
    """
    Supprimer un document
    """
    try:
        document = get_object_or_404(Document, uuid=uuid)
        document.delete()
        return Response(
            {'message': 'Document supprimé avec succès'},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def document_amend(request, uuid):
    """
    Créer un amendement d'un document existant
    Crée une nouvelle version liée au document parent
    """
    try:
        # Récupérer le document parent
        parent_document = Document.objects.get(uuid=uuid)
        
        # Préparer les données proprement (sans les fichiers)
        data = {}
        for key in request.data.keys():
            # Ne pas inclure le fichier dans les données du serializer
            if key != 'document_file':
                # Gérer les champs qui peuvent avoir plusieurs valeurs (comme categories)
                values = request.data.getlist(key)
                if len(values) > 1:
                    data[key] = values
                else:
                    data[key] = request.data.get(key)
        
        # Ajouter le parent_document
        data['parent_document'] = str(parent_document.uuid)

        # Récupérer le fichier s'il est présent
        fichier = request.FILES.get('document_file')

        # Valider le fichier PDF
        try:
            validate_pdf_file(fichier)
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Créer l'amendement avec validation
        serializer = DocumentAmendSerializer(data=data)
        if serializer.is_valid():
            amended_document = serializer.save()

            # Si un fichier est fourni, créer le média et la relation
            if fichier:
                try:
                    # Créer le média
                    media = Media.objects.create(
                        fichier=fichier,
                        description=f'Fichier de l\'amendement: {amended_document.name}'
                    )

                    # Créer la relation MediaDocument
                    MediaDocument.objects.create(
                        document=amended_document,
                        media=media
                    )
                except Exception as media_error:
                    logger.error(f"Erreur lors de la création du média: {str(media_error)}")

            # Log de l'activité
            try:
                ip_address = get_client_ip(request)
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                log_document_creation(request.user, amended_document, ip_address, user_agent)
            except Exception as log_error:
                logger.error(f"Erreur lors du logging de la création de l'amendement: {log_error}")

            response_serializer = DocumentSerializer(amended_document, context={'request': request})
            return Response(
                {
                    'message': 'Amendement créé avec succès',
                    'document': response_serializer.data
                },
                status=status.HTTP_201_CREATED
            )
        
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    
    except Document.DoesNotExist:
        return Response(
            {'error': 'Document parent introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'amendement: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def document_version_chain(request, uuid):
    """
    Récupérer toute la chaîne de versions d'un document
    Retourne tous les documents liés (parent, amendements) ordonnés par date
    """
    try:
        document = Document.objects.get(uuid=uuid)
        chain = document.get_version_chain()
        
        serializer = DocumentSerializer(chain, many=True, context={'request': request})
        return Response(
            {
                'document_uuid': str(uuid),
                'version_chain': serializer.data
            },
            status=status.HTTP_200_OK
        )
    except Document.DoesNotExist:
        return Response(
            {'error': 'Document introuvable'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la chaîne de versions: {str(e)}")
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def editions_list(request):
    """
    Récupérer la liste des éditions actives
    """
    try:
        editions = EditionDocument.objects.filter(is_active=True).order_by('title')
        data = [{'uuid': str(e.uuid), 'title': e.title, 'description': e.description} for e in editions]
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def amendements_list(request):
    """
    Récupérer la liste des amendements actifs
    """
    try:
        amendements = AmendementDocument.objects.filter(is_active=True).order_by('title')
        data = [{'uuid': str(a.uuid), 'title': a.title, 'description': a.description} for a in amendements]
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def types_document_list(request):
    """
    Récupérer la liste des types de documents actifs
    """
    try:
        types = TypeDocument.objects.filter(is_active=True).order_by('nom')
        data = [{'uuid': str(t.uuid), 'nom': t.nom, 'code': t.code, 'description': t.description} for t in types]
        return Response(data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
