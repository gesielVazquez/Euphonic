from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Renombra un usuario conservando sus calificaciones, canciones y playlists "
        "(mantiene el mismo ID interno)"
    )

    def add_arguments(self, parser):
        parser.add_argument("old_username")
        parser.add_argument("new_username")
        parser.add_argument(
            "--email",
            default=None,
            help="Nuevo email (opcional).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        old = options["old_username"]
        new = options["new_username"]

        user = User.objects.filter(username=old).first()
        if user is None:
            raise CommandError(f"No existe el usuario '{old}'.")
        if User.objects.filter(username=new).exists():
            raise CommandError(f"Ya existe un usuario llamado '{new}'.")

        ratings = user.rating_set.count()
        songs = user.songs_created.count()
        playlists = user.playlists_created.count()

        user.username = new
        fields = ["username"]
        if options["email"]:
            user.email = options["email"]
            fields.append("email")
        user.save(update_fields=fields)

        self.stdout.write(
            self.style.SUCCESS(
                f"'{old}' renombrado a '{new}'. "
                f"Conservados {ratings} calificaciones, {songs} canciones "
                f"y {playlists} playlists."
            )
        )