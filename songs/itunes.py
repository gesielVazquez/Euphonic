import json
import urllib.parse
import urllib.request


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


def search_songs(query, limit=15):
    params = urllib.parse.urlencode({
        "term": query,
        "limit": limit,
        "entity": "song",
    })
    url = f"{ITUNES_SEARCH_URL}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []

    results = []
    for item in data.get("results", []):
        genre = item.get("primaryGenreName") or ""
        if not genre and item.get("genres"):
            genre = item["genres"][0] if isinstance(item["genres"], list) else ""
        results.append({
            "track_name": item.get("trackName") or "",
            "artist_name": item.get("artistName") or "",
            "album": item.get("collectionName") or "",
            "genre": genre,
            "artwork_url": (item.get("artworkUrl100") or "").replace("100x100", "200x200"),
            "track_view_url": item.get("trackViewUrl") or "",
            "preview_url": item.get("previewUrl") or "",
            "provider": "iTunes",
        })
    return results
