from django import template

register = template.Library()


@register.filter
def dictget(d, key):
    return d.get(key)


@register.filter
def user_rating(song, user):
    return song.user_rating(user)
