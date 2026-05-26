from django.contrib import admin
from .models import Song, Rating, Playlist, PlaylistSong


class RatingInline(admin.TabularInline):
    model = Rating
    extra = 0


class PlaylistSongInline(admin.TabularInline):
    model = PlaylistSong
    extra = 0


class SongAdmin(admin.ModelAdmin):
    list_display = ["title", "artist", "genre", "average_rating", "created_by", "last_played_at"]
    list_filter = ["genre", "created_by"]
    search_fields = ["title", "artist"]
    inlines = [RatingInline]


class PlaylistAdmin(admin.ModelAdmin):
    list_display = ["__str__", "created_by", "song_count", "created_at"]
    inlines = [PlaylistSongInline]

    def song_count(self, obj):
        return obj.entries.count()
    song_count.short_description = "canciones"


admin.site.register(Song, SongAdmin)
admin.site.register(Rating)
admin.site.register(Playlist, PlaylistAdmin)
admin.site.register(PlaylistSong)
