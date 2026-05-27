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
from django.db.models import Q, Count, Avg

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
    fields = ["title", "artist", "genre", "spotify_url", "tab_url", "artwork_url"]
    success_url = reverse_lazy("song_list")

    def get_initial(self):
        initial = super().get_initial()
        for field in self.fields:
            val = self.request.GET.get(field)
            if val:
                initial[field] = val
        return initial

    def form_valid(self, form):
        title = form.cleaned_data["title"]
        artist = form.cleaned_data["artist"]
        if Song.objects.filter(title__iexact=title, artist__iexact=artist).exists():
            form.add_error("title", f"Ya existe «{title}» de {artist}.")
            return self.form_invalid(form)
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class SongUpdateView(LoginRequiredMixin, UpdateView):
    model = Song
    fields = ["title", "artist", "genre", "spotify_url", "tab_url", "artwork_url"]
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


@login_required
def dashboard_view(request):
    total_songs = Song.objects.count()
    total_ratings = Rating.objects.count()
    total_playlists = Playlist.objects.count()
    avg_all = Rating.objects.aggregate(avg=Avg("value"))["avg"]
    top_rated = (
        Song.objects.annotate(avg_r=Avg("ratings__value"))
        .filter(avg_r__isnull=False)
        .order_by("-avg_r")[:5]
    )
    worst_rated = (
        Song.objects.annotate(avg_r=Avg("ratings__value"))
        .filter(avg_r__isnull=False)
        .order_by("avg_r")[:5]
    )
    return render(request, "songs/dashboard.html", {
        "total_songs": total_songs,
        "total_ratings": total_ratings,
        "total_playlists": total_playlists,
        "avg_all": round(avg_all, 2) if avg_all else None,
        "top_rated": top_rated,
        "worst_rated": worst_rated,
    })


@login_required
def export_playlist_view(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk)
    lines = [f"Playlist #{playlist.pk} — {playlist.created_at.strftime('%d/%m/%Y %H:%M')}",
             f"Generada por: {playlist.created_by.username}",
             "=" * 40]
    for entry in playlist.entries.all():
        avg = entry.song.average_rating()
        rating_str = f"{avg:.1f}★" if avg else "—"
        lines.append(f"{entry.order}. {entry.song.title} — {entry.song.artist} [{rating_str}]")
    lines.append(f"\n{playlist.entries.count()} canciones en total.")
    return render(request, "songs/playlist_export.txt", {"content": "\n".join(lines)},
                  content_type="text/plain; charset=utf-8")


@login_required
def delete_playlist_view(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk)
    if request.method == "POST":
        playlist.delete()
        messages.success(request, "Playlist eliminada.")
        return redirect("playlist_list")
    return render(request, "songs/playlist_confirm_delete.html", {"playlist": playlist})
