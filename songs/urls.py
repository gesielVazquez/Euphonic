from django.urls import path
from .views import (
    SongListView, SongCreateView, SongUpdateView, SongDeleteView,
    rate_song, search_songs_view, generate_playlist,
    PlaylistListView, PlaylistDetailView,
    dashboard_view, export_songs_view, backfill_artwork_view, backfill_preview_view,
    export_playlist_view,
    delete_playlist_view, generate_weekly_playlist_view, import_csv_view,
    public_playlist_view, toggle_playlist_visibility_view,
)

urlpatterns = [
    path("", SongListView.as_view(), name="song_list"),
    path("nueva/", SongCreateView.as_view(), name="song_create"),
    path("buscar/", search_songs_view, name="song_search"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("dashboard/backfill-artwork/", backfill_artwork_view, name="backfill_artwork"),
    path("dashboard/backfill-preview/", backfill_preview_view, name="backfill_preview"),
    path("exportar/", export_songs_view, name="export_songs"),
    path("importar/", import_csv_view, name="import_csv"),
    path("<int:pk>/editar/", SongUpdateView.as_view(), name="song_update"),
    path("<int:pk>/eliminar/", SongDeleteView.as_view(), name="song_delete"),
    path("<int:pk>/calificar/", rate_song, name="rate_song"),
    path("playlists/", PlaylistListView.as_view(), name="playlist_list"),
    path("playlists/<int:pk>/", PlaylistDetailView.as_view(), name="playlist_detail"),
    path("playlists/<int:pk>/exportar/", export_playlist_view, name="export_playlist"),
    path("playlists/<int:pk>/eliminar/", delete_playlist_view, name="delete_playlist"),
    path("playlists/<int:pk>/compartir/", toggle_playlist_visibility_view, name="toggle_playlist_visibility"),
    path("playlists/generar/", generate_playlist, name="generate_playlist"),
    path("playlists/semanal/", generate_weekly_playlist_view, name="generate_weekly_playlist"),
    path("publico/<str:token>/", public_playlist_view, name="public_playlist"),
]
