"""
Configuration personnalisée de l'admin Django pour les jobs du scheduler
"""
from django.contrib import admin
from django_apscheduler.models import DjangoJob, DjangoJobExecution
from django import forms
from apscheduler.triggers.cron import CronTrigger
import pickle

# Désenregistrer l'admin par défaut de DjangoJob s'il existe
try:
    admin.site.unregister(DjangoJob)
except admin.sites.NotRegistered:
    pass


class DjangoJobForm(forms.ModelForm):
    """Formulaire personnalisé pour l'édition des jobs"""
    
    cron_hour = forms.IntegerField(
        label="Heure (0-23)",
        min_value=0,
        max_value=23,
        required=True,
        help_text="Heure d'exécution quotidienne (0-23)"
    )
    
    cron_minute = forms.IntegerField(
        label="Minute (0-59)",
        min_value=0,
        max_value=59,
        required=True,
        help_text="Minute d'exécution (0-59)"
    )
    
    class Meta:
        model = DjangoJob
        fields = ['id', 'next_run_time']
        readonly_fields = ['id', 'next_run_time']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si c'est une édition (instance existe), extraire l'heure et la minute du trigger actuel
        if self.instance and self.instance.pk and self.instance.job_state:
            try:
                if isinstance(self.instance.job_state, bytes):
                    job_state = pickle.loads(self.instance.job_state)
                else:
                    job_state = self.instance.job_state
                
                if isinstance(job_state, dict) and 'trigger' in job_state:
                    trigger = job_state['trigger']
                    if isinstance(trigger, CronTrigger):
                        # Extraire l'heure et la minute des fields du trigger
                        for field in trigger.fields:
                            if field.name == 'hour' and hasattr(field, 'expressions'):
                                # Le field contient les valeurs
                                hour_values = str(field).split('=')[1].strip("'")
                                if hour_values != '*':
                                    self.initial['cron_hour'] = int(hour_values)
                            elif field.name == 'minute' and hasattr(field, 'expressions'):
                                minute_values = str(field).split('=')[1].strip("'")
                                if minute_values != '*':
                                    self.initial['cron_minute'] = int(minute_values)
            except Exception as e:
                print(f"Erreur lors de l'extraction du trigger: {e}")
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Mettre à jour le trigger dans job_state avec les nouvelles valeurs
        if instance.job_state:
            try:
                if isinstance(instance.job_state, bytes):
                    job_state = pickle.loads(instance.job_state)
                else:
                    job_state = instance.job_state
                
                if isinstance(job_state, dict):
                    # Créer un nouveau trigger avec les valeurs du formulaire
                    new_trigger = CronTrigger(
                        hour=self.cleaned_data['cron_hour'],
                        minute=self.cleaned_data['cron_minute']
                    )
                    
                    # Mettre à jour le trigger dans job_state
                    job_state['trigger'] = new_trigger
                    
                    # Sérialiser à nouveau job_state
                    instance.job_state = pickle.dumps(job_state)
                    
                    print(f"✅ Trigger mis à jour: hour={self.cleaned_data['cron_hour']}, minute={self.cleaned_data['cron_minute']}")
            except Exception as e:
                print(f"❌ Erreur lors de la mise à jour du trigger: {e}")
                import traceback
                traceback.print_exc()
        
        if commit:
            instance.save()
        
        return instance


@admin.register(DjangoJob)
class DjangoJobAdmin(admin.ModelAdmin):
    """Admin personnalisé pour les jobs du scheduler"""
    
    form = DjangoJobForm
    
    list_display = ['id', 'next_run_time', 'get_trigger_info']
    readonly_fields = ['id', 'next_run_time']
    
    fieldsets = (
        ('Informations du Job', {
            'fields': ('id', 'next_run_time')
        }),
        ('Configuration du Trigger Cron', {
            'fields': ('cron_hour', 'cron_minute'),
            'description': "Definir l'heure et la minute d'execution quotidienne"
        }),
    )
    
    def get_trigger_info(self, obj):
        """Affiche les informations du trigger"""
        if obj.job_state:
            try:
                if isinstance(obj.job_state, bytes):
                    job_state = pickle.loads(obj.job_state)
                else:
                    job_state = obj.job_state
                
                if isinstance(job_state, dict) and 'trigger' in job_state:
                    trigger = job_state['trigger']
                    return str(trigger)
            except Exception:
                pass
        return "N/A"
    
    get_trigger_info.short_description = "Trigger actuel"
    
    def has_add_permission(self, request):
        """Désactiver l'ajout de jobs via l'admin (créés par le code)"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Désactiver la suppression de jobs via l'admin"""
        return False


# Admin pour DjangoJobExecution (logs d'exécution)
if not admin.site.is_registered(DjangoJobExecution):
    @admin.register(DjangoJobExecution)
    class DjangoJobExecutionAdmin(admin.ModelAdmin):
        list_display = ['id', 'job', 'run_time', 'status']
        list_filter = ['status', 'run_time']
        readonly_fields = ['job', 'run_time', 'status', 'exception', 'traceback']
        
        def has_add_permission(self, request):
            return False
        
        def has_delete_permission(self, request, obj=None):
            return False
