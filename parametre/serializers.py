from rest_framework import serializers
from .models import (
    Appreciation, Categorie, Direction, SousDirection, ActionType, 
    NotificationSettings
)


class AppreciationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appreciation
        fields = ['uuid', 'nom', 'description', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie
        fields = ['uuid', 'nom', 'description', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class DirectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direction
        fields = ['uuid', 'nom', 'description', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class SousDirectionSerializer(serializers.ModelSerializer):
    direction_nom = serializers.CharField(source='direction.nom', read_only=True)
    
    class Meta:
        model = SousDirection
        fields = ['uuid', 'nom', 'description', 'direction', 'direction_nom', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class ActionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ActionType
        fields = ['uuid', 'nom', 'description', 'created_at', 'updated_at']
        read_only_fields = ['uuid', 'created_at', 'updated_at']


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = [
            'uuid',
            'pac_echeance_notice_days',
            'traitement_delai_notice_days',
            'suivi_mise_en_oeuvre_notice_days',
            'suivi_cloture_notice_days',
            'reminders_count_before_day',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']


