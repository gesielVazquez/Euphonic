import json
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed


DEEZER_SEARCH_URL = "https://api.deezer.com/search"
DEEZER_ALBUM_URL = "https://api.deezer.com/album"


def _album_genre(album_id):
    try:
        url = f"{DEEZER_ALBUM_URL}/{album_id}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            genres = data.get("genres", {}).get("data", [])
            return genres[0]["name"] if genres else ""
    except Exception:
        return ""


def search_songs(query, limit=15):
    params = urllib.parse.urlencode({
        "q": query,
        "limit": limit,
    })
    url = f"{DEEZER_SEARCH_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    items = data.get("data", [])
    if not items:
        return []

    album_ids = {item["album"]["id"] for item in items if item.get("album", {}).get("id")}
    album_genres = {}
    if album_ids:
        with ThreadPoolExecutor(max_workers=5) as executor:
            fut = {executor.submit(_album_genre, aid): aid for aid in album_ids}
            for f in as_completed(fut):
                album_genres[fut[f]] = f.result()

    results = []
    for item in items:
        aid = item.get("album", {}).get("id")
        genre = album_genres.get(aid, "")
        results.append({
            "track_name": item.get("title") or "",
            "artist_name": item.get("artist", {}).get("name") or "",
            "album": item.get("album", {}).get("title") or "",
            "genre": genre,
            "artwork_url": (item.get("album", {}).get("cover_medium") or ""),
            "track_view_url": item.get("link") or "",
            "preview_url": item.get("preview") or "",
            "provider": "Deezer",
        })
    return results
