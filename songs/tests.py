import json
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Song, Rating, Playlist, PlaylistSong
from .itunes import search_songs as itunes_search
from .deezer import search_songs as deezer_search
from .providers import search_songs as provider_search
from .views import _song_weight, _weighted_sample


class ItunesTest(TestCase):
    @patch("songs.itunes.urllib.request.urlopen")
    def test_search_songs_parses_response(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "resultCount": 2,
            "results": [
                {
                    "trackName": "Enter Sandman",
                    "artistName": "Metallica",
                    "collectionName": "Metallica",
                    "primaryGenreName": "Metal",
                    "artworkUrl100": "https://example.com/100x100.jpg",
                    "trackViewUrl": "https://example.com/track",
                    "previewUrl": "https://example.com/preview.m4a",
                },
                {
                    "trackName": "Master of Puppets",
                    "artistName": "Metallica",
                    "collectionName": "Master of Puppets",
                    "primaryGenreName": "Thrash Metal",
                    "artworkUrl100": None,
                    "trackViewUrl": None,
                    "previewUrl": None,
                },
            ],
        }).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        results = itunes_search("metallica")
        self.assertEqual(len(results), 2)

        r = results[0]
        self.assertEqual(r["track_name"], "Enter Sandman")
        self.assertEqual(r["artist_name"], "Metallica")
        self.assertEqual(r["album"], "Metallica")
        self.assertEqual(r["genre"], "Metal")
        self.assertEqual(r["artwork_url"], "https://example.com/200x200.jpg")
        self.assertEqual(r["track_view_url"], "https://example.com/track")
        self.assertEqual(r["preview_url"], "https://example.com/preview.m4a")
        self.assertEqual(r["provider"], "iTunes")

        r2 = results[1]
        self.assertEqual(r2["track_name"], "Master of Puppets")
        self.assertEqual(r2["artwork_url"], "")

    @patch("songs.itunes.urllib.request.urlopen")
    def test_search_songs_network_error_returns_empty(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("timeout")
        results = itunes_search("anything")
        self.assertEqual(results, [])

    @patch("songs.deezer.urllib.request.urlopen")
    def test_deezer_search_songs_parses_response(self, mock_urlopen):
        search_data = json.dumps({
            "data": [
                {
                    "id": 116348452,
                    "title": "Come Together (Remastered 2009)",
                    "artist": {"name": "The Beatles"},
                    "album": {"id": 12047952, "title": "Abbey Road (Remastered)", "cover_medium": "https://example.com/cover.jpg"},
                    "link": "https://deezer.com/track/1",
                    "preview": "https://example.com/preview.mp3",
                },
            ],
        })
        album_data = json.dumps({
            "genres": {"data": [{"id": 152, "name": "Rock"}]},
        })

        def side_effect(url, *args, **kwargs):
            mock = MagicMock()
            mock.__enter__.return_value = mock
            mock.read.return_value = album_data.encode() if "album" in str(url) else search_data.encode()
            return mock

        mock_urlopen.side_effect = side_effect

        results = deezer_search("come together")
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["track_name"], "Come Together (Remastered 2009)")
        self.assertEqual(r["artist_name"], "The Beatles")
        self.assertEqual(r["album"], "Abbey Road (Remastered)")
        self.assertEqual(r["genre"], "Rock")
        self.assertEqual(r["artwork_url"], "https://example.com/cover.jpg")
        self.assertEqual(r["track_view_url"], "https://deezer.com/track/1")
        self.assertEqual(r["preview_url"], "https://example.com/preview.mp3")
        self.assertEqual(r["provider"], "Deezer")

    @patch("songs.deezer.urllib.request.urlopen")
    def test_deezer_search_network_error_returns_empty(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("timeout")
        results = deezer_search("anything")
        self.assertEqual(results, [])

    @patch("songs.deezer.urllib.request.urlopen")
    def test_provider_fallback_to_itunes(self, mock_deezer):
        mock_deezer.side_effect = Exception("Deezer down")
        with patch("songs.itunes.urllib.request.urlopen") as mock_itunes:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps({
                "resultCount": 1,
                "results": [{
                    "trackName": "Enter Sandman",
                    "artistName": "Metallica",
                    "collectionName": "Metallica",
                    "primaryGenreName": "Metal",
                    "artworkUrl100": "https://example.com/100x100.jpg",
                    "trackViewUrl": "",
                    "previewUrl": "",
                }],
            }).encode()
            mock_itunes.return_value.__enter__.return_value = mock_resp

            results = provider_search("metallica")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["provider"], "iTunes")

    @patch("songs.itunes.urllib.request.urlopen")
    def test_search_songs_empty_results(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"resultCount": 0, "results": []}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        results = itunes_search("xyznonexistent")
        self.assertEqual(results, [])


class SearchSongsViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass123")
        self.client = Client()
        self.client.login(username="testuser", password="pass123")

    @patch("songs.views.provider_search")
    def test_search_view_with_query(self, mock_search):
        mock_search.return_value = [
            {"track_name": f"Song {i}", "artist_name": "Artist", "album": "Album",
             "genre": "Rock", "artwork_url": "", "track_view_url": "", "preview_url": "",
             "provider": "Deezer"}
            for i in range(15)
        ]
        resp = self.client.get(reverse("song_search"), {"q": "test"})
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "songs/song_search.html")
        self.assertIn("page_obj", resp.context)
        self.assertEqual(resp.context["query"], "test")
        self.assertEqual(len(resp.context["page_obj"]), 10)

    @patch("songs.views.provider_search")
    def test_search_view_pagination(self, mock_search):
        mock_search.return_value = [
            {"track_name": f"Song {i}", "artist_name": "Artist", "album": "Album",
             "genre": "Rock", "artwork_url": "", "track_view_url": "", "preview_url": "",
             "provider": "Deezer"}
            for i in range(25)
        ]
        resp = self.client.get(reverse("song_search"), {"q": "test", "page": 2})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context["page_obj"]), 10)
        self.assertEqual(resp.context["page_obj"].number, 2)
        self.assertEqual(resp.context["page_obj"].paginator.num_pages, 3)

    @patch("songs.views.provider_search")
    def test_search_view_no_query_shows_empty(self, mock_search):
        resp = self.client.get(reverse("song_search"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["query"], "")
        self.assertEqual(resp.context["page_obj"].paginator.count, 0)

    def test_search_view_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("song_search"), {"q": "test"})
        self.assertEqual(resp.status_code, 302)


class SongCreateViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass123")
        self.client = Client()
        self.client.login(username="testuser", password="pass123")

    def test_create_song(self):
        resp = self.client.post(reverse("song_create"), {
            "title": "Test Song",
            "artist": "Test Artist",
            "genre": "Rock",
            "spotify_url": "https://example.com",
        })
        self.assertRedirects(resp, reverse("song_list"))
        self.assertTrue(Song.objects.filter(title="Test Song").exists())
        song = Song.objects.get(title="Test Song")
        self.assertEqual(song.created_by, self.user)

    def test_create_song_prefills_from_get(self):
        resp = self.client.get(reverse("song_create"), {
            "title": "Pre-filled Title",
            "artist": "Pre-filled Artist",
            "genre": "Jazz",
            "spotify_url": "",
        })
        self.assertEqual(resp.status_code, 200)
        form = resp.context["form"]
        self.assertEqual(form.initial["title"], "Pre-filled Title")
        self.assertEqual(form.initial["artist"], "Pre-filled Artist")
        self.assertEqual(form.initial["genre"], "Jazz")


class RateSongTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass123")
        self.client = Client()
        self.client.login(username="testuser", password="pass123")
        self.song = Song.objects.create(
            title="Test", artist="Artist", genre="Rock",
            created_by=self.user,
        )

    def test_rate_song(self):
        resp = self.client.post(reverse("rate_song", args=[self.song.pk]), {"value": 4})
        self.assertRedirects(resp, reverse("song_list"))
        rating = Rating.objects.get(song=self.song, user=self.user)
        self.assertEqual(rating.value, 4)

    def test_rate_song_update(self):
        Rating.objects.create(song=self.song, user=self.user, value=2)
        resp = self.client.post(reverse("rate_song", args=[self.song.pk]), {"value": 5})
        rating = Rating.objects.get(song=self.song, user=self.user)
        self.assertEqual(rating.value, 5)

    def test_rate_song_invalid_value(self):
        resp = self.client.post(reverse("rate_song", args=[self.song.pk]), {"value": 6})
        self.assertFalse(Rating.objects.filter(song=self.song, user=self.user).exists())


class SongWeightTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("u", password="p")
        self.song = Song.objects.create(title="T", artist="A", created_by=self.user)

    def test_weight_no_ratings(self):
        self.assertEqual(_song_weight(self.song), 1.0)

    def test_weight_with_ratings(self):
        Rating.objects.create(song=self.song, user=self.user, value=3)
        self.assertEqual(_song_weight(self.song), 9.0)


class WeightedSampleTest(TestCase):
    def test_sample_size_equals_population(self):
        pop = ["a", "b", "c"]
        result = _weighted_sample(pop, [1, 1, 1], 3)
        self.assertEqual(sorted(result), sorted(pop))

    def test_sample_size_smaller(self):
        pop = ["a", "b", "c", "d", "e"]
        result = _weighted_sample(pop, [1, 1, 1, 1, 1], 3)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(item in pop for item in result))
        self.assertEqual(len(set(result)), 3)

    def test_sample_no_replacement(self):
        pop = ["a", "b", "c", "d", "e"]
        weights = [100, 1, 1, 1, 1]
        result = _weighted_sample(pop, weights, 3)
        self.assertIn("a", result)


class GeneratePlaylistTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass123")
        self.client = Client()
        self.client.login(username="testuser", password="pass123")
        self.songs = []
        for i in range(10):
            s = Song.objects.create(
                title=f"Song {i}", artist="Artist", genre="Rock",
                created_by=self.user,
            )
            self.songs.append(s)

    def test_generate_playlist_creates_correct_size(self):
        resp = self.client.get(reverse("generate_playlist"))
        playlist = Playlist.objects.first()
        self.assertIsNotNone(playlist)
        self.assertGreaterEqual(playlist.entries.count(), 8)
        self.assertLessEqual(playlist.entries.count(), 10)

    def test_generate_playlist_updates_last_played_at(self):
        self.client.get(reverse("generate_playlist"))
        playlist = Playlist.objects.first()
        for entry in playlist.entries.all():
            self.assertIsNotNone(entry.song.last_played_at)

    def test_generate_playlist_few_songs(self):
        Song.objects.all().delete()
        s = Song.objects.create(title="Only One", artist="A", created_by=self.user)
        resp = self.client.get(reverse("generate_playlist"))
        self.assertFalse(Playlist.objects.exists())
