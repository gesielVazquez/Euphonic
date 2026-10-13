# ♫ Euphonic

Lista colaborativa de canciones para el grupo. Cada integrante propone, califica y
programa estados de avance sobre las canciones que quiere tocar.

- **Stack:** Python 3.10 · Django 5.2 · SQLite (local) / PostgreSQL (Render)
- **Producción:** https://euphonic-id2r.onrender.com
- **Repo:** https://github.com/gesielVazquez/Euphonic

## Funcionalidades

- Lista de canciones agrupadas por artista, con búsqueda.
- Búsqueda en iTunes / Deezer para sumar canciones con portada y preview de audio.
- Enlaces a Spotify (search/guardado) y tablaturas.
- Calificación de 1 a 5 estrellas por usuario y promedio por canción.
- Playlists generadas por algoritmo de peso `rating²` y sin repetir canciones
  jugadas hace menos de 15 días (relaja el filtro progresivamente).
- **Estados de canción (v1.1):** Propuesta → En Proceso → Completa.
  - Botón de ciclo con color (azul / ámbar / verde) que guarda vía AJAX sin
    recargar la página.
  - Las tarjetas llevan un borde del color del estado.
  - El dashboard muestra el conteo por estado.
- Estadísticas: totales, mejor/peor calificadas, exportación CSV e importación.
- **Grabaciones de sesión (v2.2):** cada canción puede registrar sus grabaciones de
  ensayo. El audio vive en **SoundCloud** (como las canciones viven en Spotify) y la
  app guarda título + enlace + nota.
  - Título autogenerado: `aaaa/mm/dd-NOMBRE DE LA CANCION-NOMBRE DEL USUARIO`, con la
    fecha del día de la grabación (no la de subida).
  - Se comparte el **Secret link** de SoundCloud y el botón "▶ Escuchar" lo abre.
  - No se almacenan archivos en Euphonic ni se necesitan variables extra.

## Estructura

```
Euphonic/
├── euphonic/           # Config Django (settings, urls, wsgi)
├── songs/              # App principal (models, views, urls, itunes/providers)
│   ├── management/     # setup_users, rename_user
│   └── templates/      # base + templates de songs
├── render.yaml         # Plantilla de Blueprint (futuro: Preview Environments)
├── AGENTS.md           # Notas de contexto del proyecto
└── requirements.txt
```

## Desarrollo local

```bash
DJANGO_SECRET_KEY=tests DJANGO_DEBUG=True .venv/bin/python manage.py runserver
```

- Archivo de BD local: `db.sqlite3` (no commiteado).
- Por defecto `DJANGO_DEBUG=True` y `DJANGO_SECRET_KEY` opcional en local.

## Despliegue en Render

- Se despliega automáticamente desde la rama `main`.
- **Build:** `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate && python manage.py setup_users`
- **Start:** `gunicorn euphonic.wsgi`
- **Env vars:** `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`,
  `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `ADMIN_*`, `USER1_*`, `USER2_*`, etc.
  (`setup_users` crea e ignora duplicados, así sumar gente es solo agregar `USERn_*`).

## Flujo de versionado y ramas

Seguimos un flujo de **rama por feature → PR → merge → tag**, para poder volver a
cualquier versión si algo falla.

1. `main` es **siempre la versión estable** que está en Render.
2. Cada prueba va en su rama (`feature/...`) creada desde `main`.
3. Se integra con un **Pull Request** (historial + botón Revert).
4. Al aprobar se mergea a `main`, Render despliega, y se marca un **tag** de versión.

| Tag | Versión |
|-----|---------|
| `v1.0-spotify-qr` | Base estable (botón Spotify search + filtro `qr_url`) |
| `v1.1` | Estados de canción: botón de ciclo, borde por estado, estadísticas |
| `v1.1.1` | Cambio de estado vía AJAX (sin recargar la página) |
| `v2.0` | Grabaciones de sesión (subida de archivos, backend Cloudinary) |
| `v2.1` | Grabaciones: botón ▶ Escuchar directo al CDN, sin combo de canciones |
| `v2.2` | Grabaciones en SoundCloud (enlace + fecha), se quita Cloudinary |

**Para volver a una versión buena si algo sale mal:**
- Antes de mergear: descartar la rama, `main` queda intacto.
- Después de mergear: `git revert <commit>` en `main` (Render redespliega) o
  `git checkout <tag-bueno>` para trabajar sobre esa base.

**Pruebas de la rama `main` en Render:**

- La producción es la versión commiteada en `main`; las ramas no se despliegan
  hasta el merge.
- Con Render Free esto es al pie: ver [página de carga en Render Free](#pagina-de-carga-en-render-free).

## Página de carga en Render Free

Cuando Render (plan gratuito) apaga el servicio por inactividad, al entrar muestra
la **página de carga propia de Render** mientras el contenedor vuelve a arrancar
("cold start").

- Es un placeholder de la plataforma, **no es parte de Euphonic** y **no se puede
  personalizar** (ni por dashboard ni por `render.yaml`). Lo único personalizable
  es la página de *Maintenance Mode*, que es otra cosa.
- Es comportamiento del plan Free: apaga por inactividad y el arranque es lento.
  En planes de pago la instancia queda activa y la página casi no se ve.
- No afecta a los datos de la app; es solo la espera del despertar.

## Preview Environments (futuro)

En `render.yaml` hay una plantilla preparada para **Preview Environments** (una URL
por Pull Request), pero **requieren plan Pro**. Cuando se suba de plan: crear el
environment group `euphonic-shared` en el dashboard, conectar el Blueprint y
adoptar el servicio existente (los pasos están comentados en `render.yaml`).