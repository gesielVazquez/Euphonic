from . import itunes, deezer

PROVIDER_ORDER = [deezer, itunes]


def search_songs(query, limit=15):
    for provider in PROVIDER_ORDER:
        results = provider.search_songs(query, limit)
        if results:
            return results
    return []
