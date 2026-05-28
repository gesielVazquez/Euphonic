import json
import urllib.parse
import urllib.request


DEEZER_SEARCH_URL = "https://api.deezer.com/search"


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

    results = []
    for item in data.get("data", []):
        results.append({
            "track_name": item.get("title") or "",
            "artist_name": item.get("artist", {}).get("name") or "",
            "album": item.get("album", {}).get("title") or "",
            "genre": "",
            "artwork_url": (item.get("album", {}).get("cover_medium") or ""),
            "track_view_url": item.get("link") or "",
            "preview_url": item.get("preview") or "",
            "provider": "Deezer",
        })
    return results
