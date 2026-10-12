"""Almacenamiento de grabaciones de audio.

En desarrollo y tests se usa el sistema de archivos local (media/recordings/).
En producción, si está definida la variable CLOUDINARY_URL, se usa Cloudinary
(los archivos no viven en Render). El assets se sube como tipo "authenticated"
(privado) y solo se sirve con URLs firmadas generadas por la app con login.

La interfaz es la misma para ambos backends:
solo save / read / delete usando la "storage_key" que guarda la base de datos.
"""

import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _env(name):
    value = os.environ.get(name, "").strip()
    return value or None


class RecordingsStorage:
    """Interfaz base: save / read / delete por storage_key."""

    def save(self, key, data):
        raise NotImplementedError

    def read(self, key):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError


class LocalStorage(RecordingsStorage):
    """Guarda en MEDIA/recordings — solo para desarrollo local y tests."""

    def __init__(self, root=None):
        base = root or settings.MEDIA_ROOT or (settings.BASE_DIR / "media")
        self.root = Path(base) / "recordings"
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key):
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("storage_key inválida: intento de escape de directorio")
        return path

    def save(self, key, data):
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(data, "chunks"):
            with path.open("wb") as fh:
                for chunk in data.chunks():
                    fh.write(chunk)
        else:
            path.write_bytes(data)
        return key

    def read(self, key):
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError:
            return None

    def delete(self, key):
        self._path(key).unlink(missing_ok=True)


class CloudinaryStorage(RecordingsStorage):
    """Almacena en Cloudinary con entrega privada (type=authenticated).

    Los assets se suben como raw (sin transcodeo → no consume créditos de
    procesamiento) y las URLs de descarga se firman por request (sign_url=True).
    """

    def __init__(self):
        from cloudinary import api, config, uploader, utils
        config(secure=True)
        cfg = config()
        if not (cfg.cloud_name and cfg.api_key and cfg.api_secret):
            raise ImproperlyConfigured(
                "La variable CLOUDINARY_URL es necesaria para el almacenamiento "
                "en Cloudinary (ej: cloudinary://KEY:SECRET@CLOUD_NAME)."
            )
        self._uploader = uploader
        self._api = api
        self._utils = utils

    def save(self, key, data):
        if hasattr(data, "read"):
            data = data.read()
        self._uploader.upload(
            data,
            public_id=key,
            resource_type="raw",
            type="authenticated",
            overwrite=True,
        )
        return key

    def read(self, key):
        try:
            url = self._utils.cloudinary_url(
                key, resource_type="raw", type="authenticated", sign_url=True
            )[0]
            with urllib.request.urlopen(url) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 400):
                return None
            raise

    def delete(self, key):
        try:
            self._api.delete_resources(
                [key], resource_type="raw", type="authenticated"
            )
        except Exception:
            pass


def get_storage():
    """Devuelve el backend adecuado según el entorno."""
    if _env("CLOUDINARY_URL"):
        return CloudinaryStorage()
    if settings.DEBUG or "test" in sys.argv:
        return LocalStorage()
    raise ImproperlyConfigured(
        "El almacenamiento de grabaciones no está configurado. Definí la "
        "variable CLOUDINARY_URL en producción."
    )