import time
from django.core.management.base import BaseCommand
from songs.models import Song
from songs.itunes import search_songs


class Command(BaseCommand):
    help = "Busca carátulas faltantes en iTunes para canciones sin artwork_url"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué canciones se actualizarían sin modificar nada",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        songs = Song.objects.filter(artwork_url="")
        total = songs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Todas las canciones ya tienen carátula."))
            return

        self.stdout.write(f"Buscando carátulas para {total} canciones…")
        updated = 0
        errors = 0

        for song in songs:
            query = f"{song.title} {song.artist}"
            results = search_songs(query, limit=3)
            artwork = ""
            for r in results:
                if r["artwork_url"]:
                    artwork = r["artwork_url"]
                    break

            if artwork:
                if dry_run:
                    self.stdout.write(f"  [{song.pk}] {song.title} — {song.artist} → {artwork}")
                else:
                    song.artwork_url = artwork
                    song.save(update_fields=["artwork_url"])
                updated += 1
            else:
                self.stdout.write(self.style.WARNING(f"  Sin resultados: {song.title} — {song.artist}"))
                errors += 1

            time.sleep(0.3)

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"\nSe actualizarían {updated} canciones."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nActualizadas {updated} canciones. {errors} sin resultados."))
