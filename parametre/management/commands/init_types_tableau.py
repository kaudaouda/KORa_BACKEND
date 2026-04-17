from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Obsolète — le modèle Versions a été supprimé (remplacé par num_amendement).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            'Cette commande est obsolète. '
            'Le modèle Versions a été supprimé et remplacé par num_amendement.'
        ))
