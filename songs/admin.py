from django.contrib import admin
from .models import Song, Rating, Playlist, PlaylistSong, Recording


class RatingInline(admin.TabularInline):
    model = Rating
    extra = 0


class PlaylistSongInline(admin.TabularInline):
    model = PlaylistSong
    extra = 0


class RecordingInline(admin.TabularInline):
    model = Recording
    extra = 0
    readonly_fields = ["uploaded_by", "created_at"]


class SongAdmin(admin.ModelAdmin):
    list_display = ["title", "artist", "genre", "average_rating", "created_by", "last_played_at", "artwork_url"]
    list_filter = ["genre", "created_by"]
    search_fields = ["title", "artist"]
    inlines = [RatingInline, RecordingInline]


class PlaylistAdmin(admin.ModelAdmin):
    list_display = ["__str__", "created_by", "song_count", "is_public", "created_at"]
    inlines = [PlaylistSongInline]

    def song_count(self, obj):
        return obj.entries.count()
    song_count.short_description = "canciones"


class RecordingAdmin(admin.ModelAdmin):
    list_display = ["title", "song", "uploaded_by", "url", "created_at"]
    list_filter = ["song", "uploaded_by"]
    search_fields = ["title", "note", "url"]
    readonly_fields = ["uploaded_by", "created_at"]


admin.site.register(Song, SongAdmin)
admin.site.register(Rating)
admin.site.register(Playlist, PlaylistAdmin)
admin.site.register(PlaylistSong)
admin.site.register(Recording, RecordingAdmin)
