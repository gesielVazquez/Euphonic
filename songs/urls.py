from django.urls import path
from .views import (
    SongListView, SongCreateView, SongUpdateView, SongDeleteView,
    rate_song, search_songs_view, generate_playlist,
    PlaylistListView, PlaylistDetailView,
    dashboard_view, export_playlist_view, delete_playlist_view,
)

urlpatterns = [
    path("", SongListView.as_view(), name="song_list"),
    path("nueva/", SongCreateView.as_view(), name="song_create"),
    path("buscar/", search_songs_view, name="song_search"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("<int:pk>/editar/", SongUpdateView.as_view(), name="song_update"),
    path("<int:pk>/eliminar/", SongDeleteView.as_view(), name="song_delete"),
    path("<int:pk>/calificar/", rate_song, name="rate_song"),
    path("playlists/", PlaylistListView.as_view(), name="playlist_list"),
    path("playlists/<int:pk>/", PlaylistDetailView.as_view(), name="playlist_detail"),
    path("playlists/<int:pk>/exportar/", export_playlist_view, name="export_playlist"),
    path("playlists/<int:pk>/eliminar/", delete_playlist_view, name="delete_playlist"),
    path("playlists/generar/", generate_playlist, name="generate_playlist"),
]
