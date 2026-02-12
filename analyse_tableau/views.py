from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from decimal import Decimal

from .models import AnalyseTableau, AnalyseLigne, AnalyseAction
from .serializers import (
    AnalyseTableauSerializer,
    AnalyseLigneSerializer,
    AnalyseLigneFromTableauCreateSerializer,
    AnalyseLigneUpdateSerializer,
    AnalyseActionSerializer,
    AnalyseActionCreateSerializer,
    AnalyseActionUpdateSerializer,
)
from dashboard.models import TableauBord, Objectives, Indicateur
from parametre.models import Periodicite, Cible

# Import des classes de permissions pour l'analyse tableau
from permissions.permissions import (
    AnalyseTableauCreatePermission,
    AnalyseLigneCreatePermission,
    AnalyseLigneUpdatePermission,
    AnalyseActionCreatePermission,
    AnalyseActionUpdatePermission,
    AnalyseActionDeletePermission,
)


@api_view(['POST'])
@permission_classes([IsAuthenticated, AnalyseTableauCreatePermission])
def create_analyse_tableau(request):
    """
    Créer une analyse pour un tableau de bord donné.
    Body JSON attendu :
    {
      "tableau_bord_uuid": "<uuid_du_tableau>"
    }

    Security by Design :
    - Les permissions sont vérifiées AVANT cette fonction via AnalyseTableauCreatePermission
    - Empêche la création multiple d'une analyse pour le même tableau.

    Retourne 201 + analyse complète si succès.
    """
    serializer = AnalyseTableauSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Security by Design : La vérification des permissions est maintenant gérée par AnalyseTableauCreatePermission
    # via le décorateur @permission_classes

    # Création via le serializer (utilise request.user pour cree_par)
    instance = serializer.save()
    return Response(
        AnalyseTableauSerializer(instance).data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_analyse_by_tableau(request, tableau_uuid):
    """
    Récupérer l'analyse associée à un tableau de bord (par UUID du tableau).

    Security by Design :
    - Tous les utilisateurs authentifiés peuvent lire l'analyse (lecture publique)
    """
    try:
        tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_uuid)
    except TableauBord.DoesNotExist:
        return Response(
            {'detail': 'Tableau de bord introuvable.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Security by Design : Tous les utilisateurs authentifiés peuvent lire l'analyse (lecture publique)

    try:
        analyse = AnalyseTableau.objects.prefetch_related(
            'lignes',
            'lignes__actions',
            'lignes__actions__responsables_directions',
            'lignes__actions__responsables_sous_directions'
        ).get(tableau_bord=tableau)
    except AnalyseTableau.DoesNotExist:
        return Response(
            {'detail': "Aucune analyse n'est définie pour ce tableau de bord."},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = AnalyseTableauSerializer(analyse)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated, AnalyseLigneCreatePermission])
def create_ligne_from_tableau(request):
    """
    Créer une ligne d'analyse pré-remplie à partir d'un objectif,
    d'un indicateur et d'un trimestre (période).

    Body JSON attendu :
    {
      "tableau_bord_uuid": "<uuid_tableau>",
      "objective_uuid": "<uuid_objectif>",
      "indicateur_uuid": "<uuid_indicateur>",
      "periode": "T1" | "T2" | "T3" | "T4" | ...
    }

    Remplissages :
    - Objectif non atteint = libellé de l'objectif
    - Cible = condition + valeur de la Cible de l'indicateur (ex: "≥ 70%")
    - Résultat = taux de la Periodicite pour la période choisie (ex: "75%")

    Security by Design :
    - Les permissions sont vérifiées AVANT cette fonction via AnalyseLigneCreatePermission
    """
    input_serializer = AnalyseLigneFromTableauCreateSerializer(data=request.data)
    if not input_serializer.is_valid():
        return Response(input_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    data = input_serializer.validated_data
    tableau_uuid = data['tableau_bord_uuid']
    objective_uuid = data['objective_uuid']
    indicateur_uuid = data['indicateur_uuid']
    periode = data['periode']

    # 1) Récupérer le tableau
    # Security by Design : La vérification des permissions est maintenant gérée par AnalyseLigneCreatePermission
    try:
        tableau = TableauBord.objects.select_related('processus').get(uuid=tableau_uuid)
    except TableauBord.DoesNotExist:
        return Response(
            {'detail': 'Tableau de bord introuvable.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # 2) Récupérer l'objectif (et vérifier qu'il appartient bien au tableau)
    try:
        objectif = Objectives.objects.get(uuid=objective_uuid, tableau_bord=tableau)
    except Objectives.DoesNotExist:
        return Response(
            {'detail': 'Objectif introuvable pour ce tableau.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # 3) Récupérer l'indicateur lié à cet objectif
    try:
        indicateur = Indicateur.objects.get(uuid=indicateur_uuid, objective_id=objectif)
    except Indicateur.DoesNotExist:
        return Response(
            {'detail': 'Indicateur introuvable pour cet objectif.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # 4) Récupérer la périodicité (trimestre) pour cet indicateur
    try:
        periodicite = Periodicite.objects.get(indicateur_id=indicateur, periode=periode)
    except Periodicite.DoesNotExist:
        return Response(
            {'detail': "Aucune périodicité trouvée pour cet indicateur et cette période."},
            status=status.HTTP_404_NOT_FOUND
        )

    # 5) Récupérer la cible de l'indicateur
    cible_str = ''
    cible_obj = None
    try:
        cible_obj = Cible.objects.filter(indicateur_id=indicateur).first()
        if cible_obj:
            cible_str = f"{cible_obj.condition} {cible_obj.valeur}%"
    except Exception:
        # En cas d'erreur, on laisse la cible vide mais on ne bloque pas la création
        cible_obj = None
        cible_str = ''

    # 5bis) Security by Design : Ne permettre l'analyse que si l'objectif n'est PAS atteint pour cette période
    if cible_obj is not None and periodicite.taux is not None:
        try:
            # periodicite.taux est un pourcentage (ex: 75.0)
            valeur_reelle = Decimal(str(periodicite.taux))
        except (ValueError, TypeError):
            # Si la conversion échoue, on considère que l'objectif n'est pas atteint
            valeur_reelle = None

        if valeur_reelle is not None and cible_obj.is_objectif_atteint(valeur_reelle):
            # Security by Design : on bloque la création côté backend
            return Response(
                {
                    'detail': (
                        "L'objectif est déjà atteint pour cette période, "
                        "aucune analyse n'est requise."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

    # 6) Récupérer ou créer l'AnalyseTableau pour ce tableau
    analyse, _ = AnalyseTableau.objects.get_or_create(
        tableau_bord=tableau,
        defaults={'cree_par': request.user}
    )

    # Security by Design : Vérifier qu'il n'existe pas déjà une ligne pour ce trimestre
    if AnalyseLigne.objects.filter(analyse_tableau=analyse, periode=periode).exists():
        return Response(
            {'detail': f'Une ligne d\'analyse existe déjà pour le trimestre {periode}.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 7) Créer la ligne d'analyse pré-remplie
    resultat_str = f"{periodicite.taux}%" if periodicite.taux is not None else ''

    ligne = AnalyseLigne.objects.create(
        analyse_tableau=analyse,
        periode=periode,
        objectif_non_atteint=objectif.libelle,
        cible=cible_str,
        resultat=resultat_str,
        causes='',
    )

    output_serializer = AnalyseLigneSerializer(ligne)
    return Response(output_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, AnalyseLigneUpdatePermission])
def update_ligne(request, ligne_uuid):
    """
    Mettre à jour une ligne d'analyse (notamment le champ 'causes').

    Body JSON attendu (PATCH partiel) :
    {
      "causes": "Texte des causes..."
    }

    Security by Design :
    - Les permissions sont vérifiées AVANT cette fonction via AnalyseLigneUpdatePermission
    - Seuls les champs modifiables peuvent être mis à jour (causes).
    - Les champs calculés (objectif, cible, résultat) ne peuvent pas être modifiés.
    """
    try:
        ligne = AnalyseLigne.objects.select_related(
            'analyse_tableau',
            'analyse_tableau__tableau_bord',
            'analyse_tableau__tableau_bord__processus'
        ).get(uuid=ligne_uuid)
    except AnalyseLigne.DoesNotExist:
        return Response(
            {'detail': 'Ligne d\'analyse introuvable.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Security by Design : La vérification des permissions est maintenant gérée par AnalyseLigneUpdatePermission
    # via le décorateur @permission_classes

    # Utiliser le serializer de mise à jour (ne permet que 'causes')
    serializer = AnalyseLigneUpdateSerializer(ligne, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Sauvegarder les modifications
    serializer.save()

    # Retourner la ligne complète avec le serializer complet
    output_serializer = AnalyseLigneSerializer(ligne)
    return Response(output_serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated, AnalyseActionCreatePermission])
def create_action(request):
    """
    Créer une action pour une ligne d'analyse.

    Body JSON attendu :
    {
      "ligne": "<uuid_ligne>",
      "action": "Description de l'action...",
      "responsables_directions": [<uuid1>, <uuid2>],
      "responsables_sous_directions": [<uuid1>, <uuid2>],
      "delai_realisation": "2024-12-31",
      "etat_mise_en_oeuvre": <uuid>,
      "date_realisation": "2024-12-31",
      "preuve": <uuid>,
      "evaluation": <uuid>,
      "commentaire": "..."
    }

    Security by Design :
    - Les permissions sont vérifiées AVANT cette fonction via AnalyseActionCreatePermission
    """
    serializer = AnalyseActionCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Le serializer DRF convertit automatiquement l'UUID en objet AnalyseLigne
    ligne = serializer.validated_data.get('ligne')
    
    # Recharger la ligne avec les relations nécessaires
    ligne = AnalyseLigne.objects.select_related(
        'analyse_tableau',
        'analyse_tableau__tableau_bord',
        'analyse_tableau__tableau_bord__processus'
    ).get(uuid=ligne.uuid)

    # Security by Design : La vérification des permissions est maintenant gérée par AnalyseActionCreatePermission
    # via le décorateur @permission_classes

    # Mettre à jour validated_data avec la ligne chargée (pour éviter les problèmes de relations)
    serializer.validated_data['ligne'] = ligne

    # Créer l'action
    action = serializer.save()

    # Retourner l'action créée
    output_serializer = AnalyseActionSerializer(action)
    return Response(output_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, AnalyseActionUpdatePermission])
def update_action(request, action_uuid):
    """
    Mettre à jour une action d'analyse.

    Body JSON attendu (PATCH partiel) :
    {
      "action": "Description modifiée...",
      "responsables_directions": [<uuid1>, <uuid2>],
      ...
    }

    Security by Design :
    - Les permissions sont vérifiées AVANT cette fonction via AnalyseActionUpdatePermission
    """
    try:
        action = AnalyseAction.objects.select_related(
            'ligne',
            'ligne__analyse_tableau',
            'ligne__analyse_tableau__tableau_bord',
            'ligne__analyse_tableau__tableau_bord__processus'
        ).get(uuid=action_uuid)
    except AnalyseAction.DoesNotExist:
        return Response(
            {'detail': 'Action d\'analyse introuvable.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Security by Design : La vérification des permissions est maintenant gérée par AnalyseActionUpdatePermission
    # via le décorateur @permission_classes

    # Utiliser le serializer de mise à jour
    serializer = AnalyseActionUpdateSerializer(action, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Sauvegarder les modifications
    serializer.save()

    # Retourner l'action mise à jour
    output_serializer = AnalyseActionSerializer(action)
    return Response(output_serializer.data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, AnalyseActionDeletePermission])
def delete_action(request, action_uuid):
    """
    Supprimer une action d'analyse.

    Security by Design :
    - Les permissions sont vérifiées AVANT cette fonction via AnalyseActionDeletePermission
    """
    try:
        action = AnalyseAction.objects.select_related(
            'ligne',
            'ligne__analyse_tableau',
            'ligne__analyse_tableau__tableau_bord',
            'ligne__analyse_tableau__tableau_bord__processus'
        ).get(uuid=action_uuid)
    except AnalyseAction.DoesNotExist:
        return Response(
            {'detail': 'Action d\'analyse introuvable.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Security by Design : La vérification des permissions est maintenant gérée par AnalyseActionDeletePermission
    # via le décorateur @permission_classes

    # Supprimer l'action
    action.delete()

    return Response(
        {'detail': 'Action supprimée avec succès.'},
        status=status.HTTP_200_OK
    )
