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
        results.append({
            "track_name": item.get("trackName"),
            "artist_name": item.get("artistName"),
            "album": item.get("collectionName"),
            "genre": item.get("primaryGenreName"),
            "artwork_url": item.get("artworkUrl100", "").replace("100x100", "200x200"),
            "track_view_url": item.get("trackViewUrl"),
            "preview_url": item.get("previewUrl"),
        })
    return results
