import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile

from django.urls import reverse
from django.contrib.auth.models import User

from .models import Song, Rating, Playlist, PlaylistSong, Recording, Tablature
from .itunes import search_songs as itunes_search
from .deezer import search_songs as deezer_search
from .providers import search_songs as provider_search
from .views import _song_weight, _weighted_sample


class RecordingTest(TestCase):
    """Registrar / escuchar (enlace SoundCloud) / eliminar grabaciones."""

    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass123")
        self.other = User.objects.create_user("other", password="pass123")
        self.song = Song.objects.create(
            title="Test", artist="Artist", genre="Rock", created_by=self.user,
        )
        self.client = Client()
        self.client.login(username="testuser", password="pass123")

    def _post(self, **overrides):
        data = {
            "song": self.song.pk,
            "fecha": "2026-10-13",
            "url": "https://soundcloud.com/usuario/test-secret-link",
            "title": "",
            "note": "",
        }
        data.update(overrides)
        return self.client.post(reverse("recording_upload"), data)

    def test_add_recording_with_link(self):
        resp = self._post()
        self.assertRedirects(resp, reverse("song_list"))
        rec = Recording.objects.get(song=self.song)
        self.assertEqual(rec.uploaded_by, self.user)
        self.assertEqual(rec.url, "https://soundcloud.com/usuario/test-secret-link")
        self.assertRegex(rec.title, r"^\d{4}/\d{2}/\d{2}-Test-testuser$")

    def test_add_recording_custom_title(self):
        self._post(title="La chispa del martes")
        rec = Recording.objects.get(song=self.song)
        self.assertEqual(rec.title, "La chispa del martes")

    def test_upload_rejects_missing_url(self):
        resp = self._post(url="")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Recording.objects.exists())

    def test_upload_rejects_non_http_url(self):
        resp = self._post(url="no-es-un-enlace")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Recording.objects.exists())

    def test_upload_rejects_invalid_date(self):
        resp = self._post(fecha="no-es-una-fecha")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Recording.objects.exists())

    def test_upload_requires_login(self):
        self.client.logout()
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)
        self.assertFalse(Recording.objects.exists())

    def test_delete_requires_owner_or_superuser(self):
        rec = Recording.objects.create(
            song=self.song, title="T",
            url="https://soundcloud.com/usuario/x",
            uploaded_by=self.user,
        )
        self.client.login(username="other", password="pass123")
        self.client.post(reverse("recording_delete", args=[rec.pk]))
        self.assertTrue(Recording.objects.filter(pk=rec.pk).exists())

        self.client.login(username="testuser", password="pass123")
        self.client.post(reverse("recording_delete", args=[rec.pk]))
        self.assertFalse(Recording.objects.filter(pk=rec.pk).exists())

    def test_upload_form_without_song_shows_guidance(self):
        resp = self.client.get(reverse("recording_upload"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "primero elegí la canción")

    def test_song_list_shows_recordings_with_link(self):
        Recording.objects.create(
            song=self.song, title="Mi grabación",
            url="https://soundcloud.com/usuario/secret",
            uploaded_by=self.user,
        )
        resp = self.client.get(reverse("song_list"))
        self.assertContains(resp, "Mi grabación")
        self.assertContains(resp, "🎙 Grabaciones")
        self.assertContains(resp, "https://soundcloud.com/usuario/secret")

    def test_upload_form_has_soundcloud_help(self):
        resp = self.client.get(reverse("recording_upload"), {"song": self.song.pk})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "SoundCloud")
        self.assertContains(resp, "Secret link")

    def test_song_list_upload_button(self):
        resp = self.client.get(reverse("song_list"))
        self.assertContains(resp, reverse("recording_upload"))


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


class SongOwnershipTest(TestCase):
    """Solo el creador de la canción (o un superusuario) puede eliminarla."""

    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pass123")
        self.other = User.objects.create_user("other", password="pass123")
        self.admin = User.objects.create_superuser(
            "boss", "boss@euphonic.app", "pass123"
        )
        self.song = Song.objects.create(
            title="Test", artist="Artist", created_by=self.owner,
        )
        self.client = Client()

    def test_other_user_cannot_delete_song(self):
        self.client.login(username="other", password="pass123")
        resp = self.client.post(reverse("song_delete", args=[self.song.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Song.objects.filter(pk=self.song.pk).exists())

    def test_superuser_can_delete_song(self):
        self.client.login(username="boss", password="pass123")
        self.client.post(reverse("song_delete", args=[self.song.pk]))
        self.assertFalse(Song.objects.filter(pk=self.song.pk).exists())

    def test_owner_can_delete_song(self):
        self.client.login(username="owner", password="pass123")
        self.client.post(reverse("song_delete", args=[self.song.pk]))
        self.assertFalse(Song.objects.filter(pk=self.song.pk).exists())

    def test_other_user_can_edit_song(self):
        self.client.login(username="other", password="pass123")
        resp = self.client.post(reverse("song_update", args=[self.song.pk]), {
            "title": "Test editado",
            "artist": "Artist",
            "genre": "Rock",
        })
        self.assertEqual(resp.status_code, 302)
        self.song.refresh_from_db()
        self.assertEqual(self.song.title, "Test editado")


class TablatureTest(TestCase):
    """Tablaturas por usuario: una por canción, con opción de compartir."""

    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass123")
        self.other = User.objects.create_user("other", password="pass123")
        self.admin = User.objects.create_superuser("boss", "boss@euphonic.app", "pass123")
        self.song = Song.objects.create(
            title="Test", artist="Artist", genre="Rock", created_by=self.user,
        )
        self.client = Client()
        self.client.login(username="testuser", password="pass123")

    def _post(self, **overrides):
        data = {
            "url": "https://tabs.example.com/riffs",
            "label": "Riffs",
            "is_shared": "",
        }
        data.update(overrides)
        return self.client.post(reverse("tab_save", args=[self.song.pk]), data)

    def test_add_tab(self):
        resp = self._post()
        tab = Tablature.objects.get(song=self.song, user=self.user)
        self.assertEqual(tab.url, "https://tabs.example.com/riffs")
        self.assertEqual(tab.label, "Riffs")
        self.assertFalse(tab.is_shared)
        self.assertEqual(resp.status_code, 302)

    def test_add_tab_shared(self):
        self._post(is_shared="on")
        tab = Tablature.objects.get(song=self.song, user=self.user)
        self.assertTrue(tab.is_shared)

    def test_update_own_tab_does_not_duplicate(self):
        self._post()
        self._post(url="https://tabs.example.com/acordes", label="Acordes")
        self.assertEqual(Tablature.objects.filter(song=self.song, user=self.user).count(), 1)
        tab = Tablature.objects.get(song=self.song, user=self.user)
        self.assertEqual(tab.url, "https://tabs.example.com/acordes")
        self.assertEqual(tab.label, "Acordes")

    def test_unique_together_song_user(self):
        Tablature.objects.create(song=self.song, user=self.user, url="https://a.com/x")
        with self.assertRaises(Exception):
            Tablature.objects.create(song=self.song, user=self.user, url="https://a.com/y")

    def test_post_rejects_missing_url(self):
        resp = self._post(url="")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Tablature.objects.exists())

    def test_post_rejects_non_http_url(self):
        resp = self._post(url="no-es-un-enlace")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Tablature.objects.exists())

    def test_post_rejects_too_long_url(self):
        resp = self._post(url="https://a.com/" + "x" * 500)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Tablature.objects.exists())

    def test_save_requires_login(self):
        self.client.logout()
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)

    def test_song_list_shows_my_tab(self):
        self._post()
        resp = self.client.get(reverse("song_list"))
        self.assertContains(resp, "Mi tab")
        self.assertContains(resp, "https://tabs.example.com/riffs")
        self.assertContains(resp, "Riffs")

    def test_song_list_hides_other_private_tab(self):
        Tablature.objects.create(
            song=self.song, user=self.other,
            url="https://tabs.example.com/privada", label="Secreta",
        )
        resp = self.client.get(reverse("song_list"))
        self.assertNotContains(resp, "https://tabs.example.com/privada")
        self.assertNotContains(resp, "Secreta")

    def test_song_list_shows_shared_tab_of_other(self):
        Tablature.objects.create(
            song=self.song, user=self.other,
            url="https://tabs.example.com/compartida", label="Riffs",
            is_shared=True,
        )
        resp = self.client.get(reverse("song_list"))
        self.assertContains(resp, "https://tabs.example.com/compartida")
        self.assertContains(resp, "Tab (other)")

    def test_playlist_detail_shows_visible_tabs(self):
        self._post()
        Tablature.objects.create(
            song=self.song, user=self.other,
            url="https://tabs.example.com/privada-otro", is_shared=False,
        )
        playlist = Playlist.objects.create(created_by=self.user)
        PlaylistSong.objects.create(playlist=playlist, song=self.song, order=1)
        resp = self.client.get(reverse("playlist_detail", args=[playlist.pk]))
        self.assertContains(resp, "https://tabs.example.com/riffs")
        self.assertNotContains(resp, "https://tabs.example.com/privada-otro")

    def test_delete_requires_owner_or_superuser(self):
        self._post()
        tab = Tablature.objects.get(song=self.song, user=self.user)
        self.client.login(username="other", password="pass123")
        self.client.post(reverse("tab_delete", args=[tab.pk]))
        self.assertTrue(Tablature.objects.filter(pk=tab.pk).exists())

        self.client.login(username="boss", password="pass123")
        self.client.post(reverse("tab_delete", args=[tab.pk]))
        self.assertFalse(Tablature.objects.filter(pk=tab.pk).exists())

    def test_owner_can_delete_own_tab(self):
        self._post()
        tab = Tablature.objects.get(song=self.song, user=self.user)
        self.client.post(reverse("tab_delete", args=[tab.pk]))
        self.assertFalse(Tablature.objects.filter(pk=tab.pk).exists())

    def test_delete_requires_post(self):
        self._post()
        tab = Tablature.objects.get(song=self.song, user=self.user)
        resp = self.client.get(reverse("tab_delete", args=[tab.pk]))
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Tablature.objects.filter(pk=tab.pk).exists())

    def test_edit_song_form_has_tab_section(self):
        self._post()
        resp = self.client.get(reverse("song_update", args=[self.song.pk]))
        self.assertContains(resp, "Mi tablatura")
        self.assertContains(resp, "https://tabs.example.com/riffs")
        self.assertNotContains(resp, 'name="tab_url"')

    def test_song_create_form_has_no_tab_url_field(self):
        resp = self.client.get(reverse("song_create"))
        self.assertNotContains(resp, 'name="tab_url"')

    def test_tab_form_get_prefills_my_tab(self):
        self._post()
        resp = self.client.get(reverse("tab_save", args=[self.song.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "https://tabs.example.com/riffs")
        self.assertContains(resp, "Compartirla con el resto de la banda")

    def test_csv_export_includes_my_tab_only(self):
        self._post()
        Tablature.objects.create(
            song=self.song, user=self.other,
            url="https://tabs.example.com/otro", is_shared=True,
        )
        resp = self.client.get(reverse("export_songs"))
        content = resp.content.decode()
        self.assertIn("https://tabs.example.com/riffs", content)
        self.assertNotIn("https://tabs.example.com/otro", content)

    def test_csv_import_creates_private_tab(self):
        csv_content = (
            "title,artist,genre,spotify_url,tab_url,rating\n"
            "Importada,Artista,Rock,,https://tabs.example.com/importada,\n"
        )
        resp = self.client.post(
            reverse("import_csv"),
            {"csv_file": SimpleUploadedFile(
                "t.csv", csv_content.encode(), content_type="text/csv",
            )},
        )
        self.assertEqual(resp.status_code, 302)
        song = Song.objects.get(title="Importada")
        tab = Tablature.objects.get(song=song)
        self.assertEqual(tab.user, self.user)
        self.assertEqual(tab.url, "https://tabs.example.com/importada")
        self.assertFalse(tab.is_shared)

    def test_str_includes_song_label_and_user(self):
        tab = Tablature.objects.create(
            song=self.song, user=self.user, url="https://a.com/x", label="Riffs",
        )
        self.assertEqual(str(tab), "Test · Riffs (testuser)")


class LoginRequiredOnMutatingViewsTest(TestCase):
    """rate_song y generate_playlist deben redirigir al login, no devolver 500."""

    def setUp(self):
        self.user = User.objects.create_user("testuser", password="pass123")
        self.song = Song.objects.create(
            title="Test", artist="Artist", created_by=self.user,
        )
        for i in range(5):
            Song.objects.create(title=f"S{i}", artist="A", created_by=self.user)

    def test_rate_song_anonymous_redirects_to_login(self):
        resp = self.client.post(
            reverse("rate_song", args=[self.song.pk]), {"value": 5}
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)
        self.assertFalse(Rating.objects.exists())

    def test_generate_playlist_anonymous_redirects_to_login(self):
        resp = self.client.get(reverse("generate_playlist"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)
        self.assertFalse(Playlist.objects.exists())


class PlaylistOwnershipTest(TestCase):
    """Solo el dueño puede eliminar una playlist o cambiar su visibilidad."""

    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pass123")
        self.other = User.objects.create_user("other", password="pass123")
        self.song = Song.objects.create(
            title="Test", artist="Artist", created_by=self.owner,
        )
        self.playlist = Playlist.objects.create(created_by=self.owner)
        PlaylistSong.objects.create(playlist=self.playlist, song=self.song, order=1)
        self.client = Client()

    def test_other_user_cannot_delete_playlist(self):
        self.client.login(username="other", password="pass123")
        resp = self.client.post(reverse("delete_playlist", args=[self.playlist.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Playlist.objects.filter(pk=self.playlist.pk).exists())

    def test_other_user_cannot_toggle_visibility(self):
        self.client.login(username="other", password="pass123")
        resp = self.client.get(reverse("toggle_playlist_visibility", args=[self.playlist.pk]))
        self.assertEqual(resp.status_code, 302)
        self.playlist.refresh_from_db()
        self.assertFalse(self.playlist.is_public)

    def test_other_user_can_view_and_export_playlist(self):
        self.client.login(username="other", password="pass123")
        self.assertEqual(
            self.client.get(reverse("playlist_detail", args=[self.playlist.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("export_playlist", args=[self.playlist.pk])).status_code,
            200,
        )

    def test_owner_can_delete_and_toggle(self):
        self.client.login(username="owner", password="pass123")
        self.client.get(reverse("toggle_playlist_visibility", args=[self.playlist.pk]))
        self.playlist.refresh_from_db()
        self.assertTrue(self.playlist.is_public)

        self.client.post(reverse("delete_playlist", args=[self.playlist.pk]))
        self.assertFalse(Playlist.objects.filter(pk=self.playlist.pk).exists())

    def test_superuser_can_delete_and_toggle_others_playlist(self):
        admin = User.objects.create_superuser(
            "boss", "boss@euphonic.app", "pass123"
        )
        self.client.login(username="boss", password="pass123")
        self.client.get(reverse("toggle_playlist_visibility", args=[self.playlist.pk]))
        self.playlist.refresh_from_db()
        self.assertTrue(self.playlist.is_public)

        self.client.post(reverse("delete_playlist", args=[self.playlist.pk]))
        self.assertFalse(Playlist.objects.filter(pk=self.playlist.pk).exists())
