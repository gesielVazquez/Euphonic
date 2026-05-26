# Euphonic — Contexto del proyecto

## Stack
- Python 3.10 + Django 5.2 + SQLite (local) / PostgreSQL (producción)
- Desplegado en Render: https://euphonic-id2r.onrender.com
- Repo: https://github.com/gesielVazquez/Euphonic

## Estructura
```
Euphonic/
├── euphonic/         # Config Django (settings, urls, wsgi)
├── songs/            # App principal
│   ├── models.py     # Song, Rating, Playlist, PlaylistSong
│   ├── views.py      # CRUD, rate_song, generar playlist
│   ├── urls.py       # Rutas de la app
│   ├── admin.py      # Admin con inlines
│   ├── templatetags/ # Filtros personalizados (dictget, user_rating)
│   ├── management/commands/setup_users.py  # Crear usuarios iniciales
│   └── templates/
│       ├── base.html
│       ├── registration/login.html
│       └── songs/    # song_list, song_form, playlist_list, playlist_detail
├── requirements.txt
├── Procfile
├── runtime.txt
└── .env.example
```

## Modelos

### Song
- `title`, `artist`, `genre`
- `spotify_url`, `tab_url`
- `last_played_at` (para filtro repetición)
- `created_by` (FK User), `created_at`, `updated_at`
- `average_rating()` → promedio de todas las Ratings
- `user_rating(user)` → rating del usuario específico
- Ordenado por: `artist`, `title`

### Rating
- `song` (FK), `user` (FK), `value` (1-5), `created_at`
- `unique_together = ["song", "user"]`

### Playlist
- `created_by` (FK), `created_at`

### PlaylistSong
- `playlist` (FK), `song` (FK), `order`

## URLs principales
| Ruta | Vista |
|------|-------|
| `/` | Lista de canciones (agrupadas por artista, orden alfabético) |
| `/nueva/` | Crear canción |
| `/<pk>/editar/` | Editar canción |
| `/<pk>/eliminar/` | Eliminar canción |
| `/<pk>/calificar/` | Calificar canción (POST) |
| `/playlists/` | Lista de playlists |
| `/playlists/generar/` | Generar playlist |
| `/playlists/<pk>/` | Detalle de playlist |
| `/accounts/login/` | Login |
| `/accounts/logout/` | Logout (POST) |
| `/admin/` | Django Admin |

## Playlist — Algoritmo
- Filtro progresivo: excluye canciones con `last_played_at` < 15 días; si < 8 candidatos, relaja día a día hasta tener suficientes
- Peso = `rating²` (1 si no tiene rating)
- Selección ruleta ponderada sin reemplazo, 8-10 canciones
- Al generar: actualiza `last_played_at` de las canciones seleccionadas

## Despliegue en Render
- **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py setup_users`
- **Start Command**: `gunicorn euphonic.wsgi`
- **Env vars necesarias**:
  - `DJANGO_SECRET_KEY`
  - `DJANGO_DEBUG=False`
  - `DJANGO_ALLOWED_HOSTS=euphonic-id2r.onrender.com`
  - `DJANGO_CSRF_TRUSTED_ORIGINS=https://euphonic-id2r.onrender.com`
  - `DATABASE_URL` (PostgreSQL Internal URL)
  - `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`
  - `USER2_USERNAME`, `USER2_PASSWORD`

## Pendiente — Idea 2
Implementar búsqueda desde iTunes Search API (sin auth) o Spotify API (con registro) para extraer datos de canciones automáticamente (artista, álbum, carátula) al escribir el nombre en un buscador.

## Usuarios
- admin / contraseña elegida por el usuario
- usuario2 / contraseña elegida por el usuario
