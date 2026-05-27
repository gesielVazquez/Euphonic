import random
from datetime import timedelta

from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q

from .models import Song, Rating, Playlist, PlaylistSong
from .itunes import search_songs as itunes_search


class SongListView(LoginRequiredMixin, ListView):
    model = Song
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(title__icontains=q) | qs.filter(artist__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_ratings = {
            r.song_id: r.value
            for r in Rating.objects.filter(user=self.request.user)
        }
        context["user_ratings"] = user_ratings
        return context


class SongCreateView(LoginRequiredMixin, CreateView):
    model = Song
    fields = ["title", "artist", "genre", "spotify_url", "tab_url"]
    success_url = reverse_lazy("song_list")

    def get_initial(self):
        initial = super().get_initial()
        for field in self.fields:
            val = self.request.GET.get(field)
            if val:
                initial[field] = val
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class SongUpdateView(LoginRequiredMixin, UpdateView):
    model = Song
    fields = ["title", "artist", "genre", "spotify_url", "tab_url"]
    success_url = reverse_lazy("song_list")


class SongDeleteView(LoginRequiredMixin, DeleteView):
    model = Song
    success_url = reverse_lazy("song_list")


def rate_song(request, pk):
    song = get_object_or_404(Song, pk=pk)
    if request.method == "POST":
        value = request.POST.get("value")
        if value and value.isdigit() and 1 <= int(value) <= 5:
            Rating.objects.update_or_create(
                song=song,
                user=request.user,
                defaults={"value": int(value)},
            )
            messages.success(request, f"Calificaste «{song.title}» con {value} estrellas.")
    return redirect(request.META.get("HTTP_REFERER", "song_list"))


@login_required
def search_songs_view(request):
    results = []
    query = request.GET.get("q", "")
    if query:
        results = itunes_search(query)
    paginator = Paginator(results, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    return render(request, "songs/song_search.html", {
        "page_obj": page_obj,
        "query": query,
    })


def _song_weight(song):
    avg = song.average_rating()
    if avg is None:
        return 1.0
    return avg ** 2


def _weighted_sample(population, weights, k):
    if len(population) <= k:
        return list(population)

    indices = list(range(len(population)))
    selected = []
    for _ in range(k):
        total = sum(weights[i] for i in indices)
        r = random.random() * total
        cumulative = 0
        for i, idx in enumerate(indices):
            cumulative += weights[idx]
            if r <= cumulative:
                selected.append(population[idx])
                indices.pop(i)
                break
    return selected


class PlaylistListView(LoginRequiredMixin, ListView):
    model = Playlist
    template_name = "songs/playlist_list.html"
    context_object_name = "playlists"
    paginate_by = 20


class PlaylistDetailView(LoginRequiredMixin, DetailView):
    model = Playlist
    template_name = "songs/playlist_detail.html"


def generate_playlist(request):
    total_songs = Song.objects.count()
    if total_songs < 3:
        messages.error(request, "Se necesitan al menos 3 canciones para generar una playlist.")
        return redirect("song_list")

    now = timezone.now()

    for days_back in range(15, -1, -1):
        cutoff = now - timedelta(days=days_back)
        candidates = Song.objects.filter(
            Q(last_played_at__isnull=True) | Q(last_played_at__lt=cutoff)
        )
        if candidates.count() >= 8:
            break

    if candidates.count() < 3:
        candidates = Song.objects.all()

    candidates_list = list(candidates)
    weights = [_song_weight(s) for s in candidates_list]

    target_size = min(random.randint(8, 10), len(candidates_list))
    selected = _weighted_sample(candidates_list, weights, target_size)

    playlist = Playlist.objects.create(created_by=request.user)
    for i, song in enumerate(selected):
        PlaylistSong.objects.create(playlist=playlist, song=song, order=i + 1)
        song.last_played_at = now
        song.save(update_fields=["last_played_at"])

    messages.success(request, f"Playlist generada con {len(selected)} canciones.")
    return redirect("playlist_detail", pk=playlist.pk)
