from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from parametre.models import Direction, SousDirection, Processus


ANAC_STRUCTURE = {
    "direction_generale_services": [
        {"code": "SDG", "intitule": "Secrétariat du DG"},
        {"code": "PCT", "intitule": "Pool Conseillers Techniques"},
        {"code": "PM", "intitule": "Pool Médical"},
        {"code": "CF", "intitule": "Contrôle Financier"},
        {"code": "BPE", "intitule": "Bureau Protection de l’Environnement"},
        {"code": "CSAR", "intitule": "Coordonnateur SAR"},
        {"code": "CDP", "intitule": "Correspondant Protection des Données à caractère personnel"},
        {"code": "BCS", "intitule": "Bureau de Coordination Sûreté"},
        {"code": "CCOM", "intitule": "Chargé de la Communication"},
    ],
    "directions": [
        {
            "code": "DAAF",
            "intitule": "Affaires Administratives et Financières",
            "sous_directions": [
                {"code": "SDARH", "intitule": "Administration et Ressources Humaines"},
                {"code": "SDFC", "intitule": "Finances et Comptabilité"},
                {"code": "SDSI", "intitule": "Systèmes d’Informations"},
                {"code": "SDFO", "intitule": "Formation"},
            ],
        },
        {
            "code": "DSF",
            "intitule": "Sûreté et Facilitation",
            "sous_directions": [
                {"code": "SDCSF", "intitule": "Contrôle Sûreté et Facilitation"},
                {"code": "SDRSF", "intitule": "Règlementation Sûreté et Facilitation"},
            ],
        },
        {
            "code": "DSSC",
            "intitule": "Sécurité et Suivi de la Conformité",
            "sous_directions": [
                {"code": "SDPNS", "intitule": "Programme National de Sécurité"},
                {"code": "SDSC", "intitule": "Suivi de la Conformité"},
            ],
        },
        {
            "code": "DSV",
            "intitule": "Sécurité des Vols",
            "sous_directions": [
                {"code": "SDOA", "intitule": "Opérations Aériennes"},
                {"code": "SDNA", "intitule": "Navigabilité des Aéronefs"},
                {"code": "SDLPA", "intitule": "Licences et formation du Personnel Aéronautique"},
            ],
        },
        {
            "code": "DSNAA",
            "intitule": "Sécurité Navigation Aérienne et Aérodromes",
            "sous_directions": [
                {"code": "SDCAT", "intitule": "Circulation aérienne et télécommunications aéronautiques"},
                {"code": "SDMIA", "intitule": "Météorologie et Information Aéronautique"},
                {"code": "SDA", "intitule": "Aérodromes"},
            ],
        },
        {
            "code": "DTA",
            "intitule": "Transport Aérien",
            "sous_directions": [
                {"code": "SDLAA", "intitule": "Législation et Accords Aériens"},
                {"code": "SDCIDTA", "intitule": "Coopération Internationale et Développement du Transport Aérien"},
            ],
        },
    ],
}


class Command(BaseCommand):
    help = (
        "Seed ANAC structure into Direction, SousDirection and Processus. "
        "Nom=code, Description=intitulé. Processus: nom='PRS-' + code, description=intitulé."
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Nom utilisateur pour le champ cree_par des Processus')

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f"Utilisateur '{username}' introuvable")

        # Directions & SousDirections
        for d in ANAC_STRUCTURE['directions']:
            dir_obj, _ = Direction.objects.get_or_create(
                nom=d['code'],
                defaults={
                    'description': d['intitule'],
                    'is_active': True,
                }
            )
            # Mettre à jour la description si nécessaire
            if dir_obj.description != d['intitule']:
                dir_obj.description = d['intitule']
                dir_obj.save(update_fields=['description'])

            # Sous-directions
            for sd in d.get('sous_directions', []):
                sd_obj, _ = SousDirection.objects.get_or_create(
                    direction=dir_obj,
                    nom=sd['code'],
                    defaults={
                        'description': sd['intitule'],
                        'is_active': True,
                    }
                )
                if sd_obj.description != sd['intitule']:
                    sd_obj.description = sd['intitule']
                    sd_obj.save(update_fields=['description'])

        # Processus pour chaque Direction et SousDirection
        # Nom = 'PRS-' + code ; description = intitulé
        for d in ANAC_STRUCTURE['directions']:
            proc_name = f"PRS-{d['code']}"
            Processus.objects.get_or_create(
                nom=proc_name,
                defaults={
                    'description': d['intitule'],
                    'cree_par': user,
                    'is_active': True,
                }
            )
            for sd in d.get('sous_directions', []):
                proc_name_sd = f"PRS-{sd['code']}"
                Processus.objects.get_or_create(
                    nom=proc_name_sd,
                    defaults={
                        'description': sd['intitule'],
                        'cree_par': user,
                        'is_active': True,
                    }
                )

        self.stdout.write(self.style.SUCCESS('ANAC structure seeded successfully.'))
