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
│   ├── views.py      # CRUD, rate_song, generar playlist, buscar canciones
│   ├── urls.py       # Rutas de la app
│   ├── admin.py      # Admin con inlines
│   ├── itunes.py     # Cliente iTunes Search API
│   ├── templatetags/ # Filtros personalizados (dictget, user_rating)
│   ├── management/commands/setup_users.py  # Crear usuarios iniciales
│   └── templates/
│       ├── base.html
│       ├── registration/login.html
│       └── songs/    # song_list, song_form, song_search, playlist_list, playlist_detail
├── requirements.txt
├── Procfile
├── runtime.txt
└── .env.example
```

## Modelos

### Song
- `title`, `artist`, `genre`, `estado` (idea/progreso/completo)
- `spotify_url`, `artwork_url`, `preview_url`
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

### Recording
- `song` (FK), `title`, `url` (enlace de escucha en SoundCloud)
- `uploaded_by` (FK User), `note`, `created_at`
- El audio vive en SoundCloud (como las canciones en Spotify); Euphonic no guarda archivos.
- Título autogenerado: `aaaa/mm/dd-NOMBRE DE LA CANCION-NOMBRE DEL USUARIO` usando la fecha de la grabación.

### Tablature (v2.3)
- `song` (FK), `user` (FK), `url`, `label` (ej: Riffs, Acordes rítmicos), `is_shared`
- `unique_together = ["song", "user"]` → una tab por usuario por canción
- Visibilidad: cada usuario ve sus tabs + las compartidas (`is_shared=True`) de otros.
  Las privadas de otros no se muestran.
- Se gestionan en `/<pk>/tablatura/` (crear/editar la propia) y se eliminan por pk.
- La migración `0013` convirtió los `Song.tab_url` viejos en tabs privadas del
  creador con etiqueta `Ritmica`; el campo `tab_url` se eliminó de `Song`.

## URLs principales
| Ruta | Vista |
|------|-------|
| `/` | Lista de canciones (agrupadas por artista, orden alfabético) |
| `/nueva/` | Crear canción (soporta GET params `?title=&artist=&genre=&spotify_url=` para pre‑llenar; valida duplicados) |
| `/buscar/` | Buscar canciones en iTunes Search API y añadirlas |
| `/dashboard/` | Estadísticas: canciones, calificaciones, playlists, top |
| `/<pk>/editar/` | Editar canción |
| `/<pk>/eliminar/` | Eliminar canción |
| `/<pk>/calificar/` | Calificar canción (POST) |
| `/playlists/` | Lista de playlists (compartidas entre usuarios) |
| `/playlists/generar/` | Generar playlist |
| `/playlists/<pk>/` | Detalle de playlist |
| `/playlists/<pk>/exportar/` | Exportar playlist como texto |
| `/playlists/<pk>/eliminar/` | Eliminar playlist (POST con confirmación) |
| `/accounts/login/` | Login |
| `/accounts/logout/` | Logout (POST) |
| `/grabaciones/subir/` | Registrar grabación (enlace SoundCloud + fecha; requiere `?song=pk`) |
| `/grabaciones/<pk>/eliminar/` | Eliminar grabación (POST, solo dueño/superuser) |
| `/<pk>/tablatura/` | Crear/editar MI tablatura de la canción (GET form, POST guarda) |
| `/tablaturas/<pk>/eliminar/` | Eliminar tablatura (POST, solo dueño/superuser) |
| `/admin/` | Django Admin |

## Grabaciones (SoundCloud)
- El audio se sube a SoundCloud (privado + "Secret link") y la app guarda el enlace.
- Título autogenerado: `aaaa/mm/dd-NOMBRE DE LA CANCION-NOMBRE DEL USUARIO` con la
  fecha del ensayo (campo `fecha` en el form, por defecto hoy), no la de subida.
- Botón "▶ Escuchar" en la tarjeta abre el enlace en pestaña nueva (como Spotify).
- `Recording.url` es obligatorio al registrar; `models.Song` sin cambios.
- En v2.0/v2.1 se subía el archivo (Cloudinary); desde v2.2 solo se guarda el enlace:
  `songs/storage.py` fue eliminado y no hay env var `CLOUDINARY_URL`.

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
  - `USER1_USERNAME`, `USER1_PASSWORD`
  - `USER2_USERNAME`, `USER2_PASSWORD`
  - (opcional) `USER3_USERNAME`, `USER3_PASSWORD`, ... para más integrantes
- **Renombrar un usuario**: `python manage.py rename_user <viejo> <nuevo> [--email ...]`.
  Mantiene el mismo ID, así que conserva calificaciones, canciones y playlists.
  Ojo: cambiar `ADMIN_USERNAME` en las env vars NO renombra, crea un admin nuevo
  y deja el anterior activo como superusuario.

## Seguridad (secretos)
- **Nunca** commitear `.env`: está en `.gitignore`; los secretos reales viven en
  las env vars de Render. En el repo solo va `.env.example` con valores **vacíos**.
- **GitHub Secret scanning + Push protection** activados en el repo (bloquean
  pushes con secretos antes de que toquen el historial).
- **gitleaks vía pre-commit** local: cada commit escanea los archivos staged
  contra cientos de patrones de secretos y **frena el commit** si detecta algo.
  - Instalar una sola vez: `.venv/bin/pip install pre-commit && .venv/bin/pre-commit install`
  - Correr a mano sobre todo el repo: `.venv/bin/pre-commit run --all-files`
  - Config: `.pre-commit-config.yaml` (hook `gitleaks`, no commitear `.venv`).
- Si un secreto se expone igual: **rotar primero** (regenerar la key/env var en la
  plataforma), después purgar historial. Borrar el archivo no deshace el leak.

## Usuarios
- `manage.py setup_users` crea el admin (`ADMIN_*`, superusuario) y todos los
  `USER{n}_USERNAME`/`USER{n}_PASSWORD` que encuentre en el entorno. Es
  idempotente: no duplica usuarios en cada build. Para sumar a alguien al grupo
  basta con agregar el par de variables, sin tocar código.
- Nombres actuales: admin (superusuario), user1, user2.

## iTunes Search API
- Ruta: `/buscar/` → vista `search_songs_view`
- `songs/itunes.py`: `search_songs(query)` devuelve lista con `track_name`, `artist_name`, `album`, `genre`, `artwork_url`, `track_view_url`, `preview_url`
- Botón "Añadir" en cada resultado enlaza a `/nueva/?title=...&artist=...&genre=...&spotify_url=...` con pre‑llenado automático del formulario
