import urllib.parse

from django import template

register = template.Library()


@register.filter
def dictget(d, key):
    return d.get(key)


@register.filter
def user_rating(song, user):
    return song.user_rating(user)


@register.filter
def qr_url(url):
    """Genera una URL de Google Chart QR para la URL dada."""
    if not url:
        return ""
    try:
        encoded_url = urllib.parse.quote(url, safe='')
        return f"https://chart.googleapis.com/chart?chs=200x200&cht=qr&chl={encoded_url}&choe=UTF-8"
    except Exception:
        return ""
