from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class Song(models.Model):
    title = models.CharField(max_length=200, verbose_name="título")
    artist = models.CharField(max_length=200, verbose_name="artista")
    genre = models.CharField(max_length=100, blank=True, verbose_name="género")

    spotify_url = models.URLField(blank=True, verbose_name="enlace Spotify")
    tab_url = models.URLField(blank=True, verbose_name="enlace tablatura")
    artwork_url = models.URLField(blank=True, verbose_name="portada")

    last_played_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="última vez en playlist",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="songs_created",
        verbose_name="creado por",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "canción"
        verbose_name_plural = "canciones"
        ordering = ["artist", "title"]

    def average_rating(self):
        ratings = self.ratings.values_list("value", flat=True)
        if not ratings:
            return None
        return sum(ratings) / len(ratings)

    def user_rating(self, user):
        try:
            return self.ratings.get(user=user).value
        except:
            return None

    def __str__(self):
        return f"{self.title} — {self.artist}"


class Rating(models.Model):
    song = models.ForeignKey(
        Song, on_delete=models.CASCADE, related_name="ratings"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    value = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "calificación"
        verbose_name_plural = "calificaciones"
        unique_together = ["song", "user"]

    def __str__(self):
        return f"{self.user.username} → {self.song.title}: {self.value}"


class Playlist(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="playlists_created",
        verbose_name="creada por",
    )

    class Meta:
        verbose_name = "playlist"
        verbose_name_plural = "playlists"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Playlist #{self.pk} — {self.created_at.strftime('%d/%m/%Y %H:%M')}"


class PlaylistSong(models.Model):
    playlist = models.ForeignKey(
        Playlist, on_delete=models.CASCADE, related_name="entries"
    )
    song = models.ForeignKey(Song, on_delete=models.CASCADE)
    order = models.IntegerField(verbose_name="orden")

    class Meta:
        verbose_name = "canción en playlist"
        verbose_name_plural = "canciones en playlist"
        ordering = ["order"]

    def __str__(self):
        return f"{self.order}. {self.song.title}"
