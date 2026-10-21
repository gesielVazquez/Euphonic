from django.db import migrations


def migrate_tab_urls(apps, schema_editor):
    """Cada Song.tab_url existente pasa a ser una Tablatura privada
    del creador de la canción, con etiqueta «Ritmica»."""
    Song = apps.get_model("songs", "Song")
    Tablature = apps.get_model("songs", "Tablature")
    for song in Song.objects.exclude(tab_url="").exclude(tab_url__isnull=True):
        Tablature.objects.get_or_create(
            song=song,
            user=song.created_by,
            defaults={
                "url": song.tab_url,
                "label": "Ritmica",
                "is_shared": False,
            },
        )


def reverse_migrate_tab_urls(apps, schema_editor):
    Tablature = apps.get_model("songs", "Tablature")
    Song = apps.get_model("songs", "Song")
    for tab in Tablature.objects.all():
        song = Song.objects.filter(pk=tab.song_id).first()
        if song and not song.tab_url:
            song.tab_url = tab.url
            song.save(update_fields=["tab_url"])


class Migration(migrations.Migration):

    dependencies = [
        ("songs", "0012_tablature"),
    ]

    operations = [
        migrations.RunPython(migrate_tab_urls, reverse_migrate_tab_urls),
    ]
