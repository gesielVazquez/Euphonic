import random
from datetime import timedelta

from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Q, Count, Avg

from .models import Song, Rating, Playlist, PlaylistSong
from .providers import search_songs as provider_search


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
    fields = ["title", "artist", "genre", "spotify_url", "tab_url", "artwork_url", "preview_url"]
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
    fields = ["title", "artist", "genre", "spotify_url", "tab_url", "artwork_url", "preview_url"]
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
        results = provider_search(query)
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


def _csv_escape(val):
    s = str(val or "")
    if "," in s or '"' in s or "\n" in s:
        s = '"' + s.replace('"', '""') + '"'
    return s


@login_required
def export_playlist_view(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk)
    lines = ["order,title,artist,genre,rating"]
    for entry in playlist.entries.all():
        avg = entry.song.average_rating()
        rating_str = f"{avg:.1f}" if avg else ""
        lines.append(
            f"{entry.order},"
            f"{_csv_escape(entry.song.title)},"
            f"{_csv_escape(entry.song.artist)},"
            f"{_csv_escape(entry.song.genre)},"
            f"{rating_str}"
        )
    content = "\n".join(lines) + "\n"
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="playlist-{playlist.pk}.csv"'
    return resp


@login_required
def export_songs_view(request):
    lines = ["title,artist,genre,spotify_url,tab_url,rating"]
    for song in Song.objects.all():
        avg = song.average_rating()
        rating_str = f"{avg:.1f}" if avg else ""
        lines.append(
            f"{_csv_escape(song.title)},"
            f"{_csv_escape(song.artist)},"
            f"{_csv_escape(song.genre)},"
            f"{_csv_escape(song.spotify_url)},"
            f"{_csv_escape(song.tab_url)},"
            f"{rating_str}"
        )
    content = "\n".join(lines) + "\n"
    resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="euphonic-canciones.csv"'
    return resp


@login_required
def backfill_artwork_view(request):
    songs = Song.objects.filter(Q(artwork_url="") | Q(artwork_url__isnull=True))
    total = songs.count()
    if total == 0:
        messages.info(request, "Todas las canciones ya tienen carátula.")
        return redirect("dashboard")

    updated = 0
    errors = 0
    for song in songs:
        try:
            results = provider_search(f"{song.title} {song.artist}", limit=3)
            artwork = ""
            for r in results:
                if r["artwork_url"]:
                    artwork = r["artwork_url"]
                    break
            if artwork:
                song.artwork_url = artwork
                song.save(update_fields=["artwork_url"])
                updated += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    messages.success(request, f"Carátulas actualizadas: {updated}. Sin resultados: {errors}.")
    return redirect("dashboard")


@login_required
def backfill_preview_view(request):
    songs = Song.objects.filter(Q(preview_url="") | Q(preview_url__isnull=True))
    total = songs.count()
    if total == 0:
        messages.info(request, "Todas las canciones ya tienen preview.")
        return redirect("dashboard")
    updated = 0
    errors = 0
    for song in songs:
        try:
            results = provider_search(f"{song.title} {song.artist}", limit=3)
            preview = ""
            for r in results:
                if r.get("preview_url"):
                    preview = r["preview_url"]
                    break
            if preview:
                song.preview_url = preview
                song.save(update_fields=["preview_url"])
                updated += 1
            else:
                errors += 1
        except Exception:
            errors += 1
    messages.success(request, f"Previews actualizados: {updated}. Sin resultados: {errors}.")
    return redirect("dashboard")


@login_required
def delete_playlist_view(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk)
    if request.method == "POST":
        playlist.delete()
        messages.success(request, "Playlist eliminada.")
        return redirect("playlist_list")
    return render(request, "songs/playlist_confirm_delete.html", {"playlist": playlist})


@login_required
def generate_weekly_playlist_view(request):
    total_songs = Song.objects.count()
    if total_songs < 3:
        messages.error(request, "Se necesitan al menos 3 canciones para generar una playlist.")
        return redirect("playlist_list")

    now = timezone.now()
    week_start = now - timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute, seconds=now.second)
    if Playlist.objects.filter(created_by=request.user, created_at__gte=week_start).exists():
        messages.info(request, "Ya tenés una playlist generada esta semana.")
        return redirect("playlist_list")

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

    messages.success(request, f"Playlist semanal generada con {len(selected)} canciones.")
    return redirect("playlist_detail", pk=playlist.pk)


@login_required
def import_csv_view(request):
    if request.method == "POST" and request.FILES.get("csv_file"):
        file = request.FILES["csv_file"]
        if not file.name.endswith(".csv"):
            messages.error(request, "El archivo debe ser .csv")
            return redirect("import_csv")

        try:
            decoded = file.read().decode("utf-8-sig").splitlines()
        except Exception:
            messages.error(request, "Error al leer el archivo.")
            return redirect("import_csv")

        import csv
        reader = csv.DictReader(decoded)
        created = 0
        skipped = 0
        for row in reader:
            title = (row.get("title") or row.get("Title") or "").strip()
            artist = (row.get("artist") or row.get("Artist") or "").strip()
            if not title or not artist:
                skipped += 1
                continue
            if Song.objects.filter(title__iexact=title, artist__iexact=artist).exists():
                skipped += 1
                continue
            Song.objects.create(
                title=title,
                artist=artist,
                genre=(row.get("genre") or row.get("Genre") or "")[:100],
                spotify_url=(row.get("spotify_url") or row.get("spotify") or row.get("Spotify") or "")[:200],
                tab_url=(row.get("tab_url") or row.get("tab") or row.get("Tab") or "")[:200],
                created_by=request.user,
            )
            created += 1

        messages.success(request, f"Importadas {created} canciones. {skipped} omitidas (duplicadas o inválidas).")
        return redirect("song_list")

    return render(request, "songs/import_csv.html")


def public_playlist_view(request, token):
    playlist = get_object_or_404(Playlist, share_token=token, is_public=True)
    return render(request, "songs/playlist_public.html", {"playlist": playlist})


@login_required
def toggle_playlist_visibility_view(request, pk):
    playlist = get_object_or_404(Playlist, pk=pk)
    playlist.is_public = not playlist.is_public
    playlist.save(update_fields=["is_public"])
    msg = "pública" if playlist.is_public else "privada"
    messages.success(request, f"Playlist ahora es {msg}.")
    return redirect("playlist_detail", pk=playlist.pk)
