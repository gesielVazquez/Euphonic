from django.urls import path
from .views import (
    SongListView, SongCreateView, SongUpdateView, SongDeleteView,
    rate_song, generate_playlist,
    PlaylistListView, PlaylistDetailView,
)

urlpatterns = [
    path("", SongListView.as_view(), name="song_list"),
    path("nueva/", SongCreateView.as_view(), name="song_create"),
    path("<int:pk>/editar/", SongUpdateView.as_view(), name="song_update"),
    path("<int:pk>/eliminar/", SongDeleteView.as_view(), name="song_delete"),
    path("<int:pk>/calificar/", rate_song, name="rate_song"),
    path("playlists/", PlaylistListView.as_view(), name="playlist_list"),
    path("playlists/<int:pk>/", PlaylistDetailView.as_view(), name="playlist_detail"),
    path("playlists/generar/", generate_playlist, name="generate_playlist"),
]
