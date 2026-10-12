"""Almacenamiento de grabaciones de audio.

En desarrollo y tests se usa el sistema de archivos local (media/recordings/).
En producción, si están definidas B2_KEY_ID, B2_APPLICATION_KEY y B2_BUCKET,
se usa un bucket privado de Backblaze B2 (los archivos no viven en Render).

La interfaz es la misma para ambos backends:
solo save / read / delete usando la "storage_key" que guarda la base de datos.
"""

import io
import os
import sys
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


class B2Storage(RecordingsStorage):
    """Almacena en un bucket privado de Backblaze B2 (producción)."""

    def __init__(self, key_id=None, application_key=None, bucket=None):
        self.key_id = _env("B2_KEY_ID") or key_id
        self.application_key = _env("B2_APPLICATION_KEY") or application_key
        self.bucket_name = _env("B2_BUCKET") or bucket
        if not (self.key_id and self.application_key and self.bucket_name):
            raise ImproperlyConfigured(
                "Faltan variables B2_KEY_ID, B2_APPLICATION_KEY o B2_BUCKET "
                "para usar el almacenamiento en Backblaze B2."
            )
        from b2sdk.v2 import InMemoryAccountInfo, B2Api
        info = InMemoryAccountInfo()
        self.api = B2Api(info)
        self.api.authorize_account("production", self.key_id, self.application_key)
        self.bucket = self.api.get_bucket_by_name(self.bucket_name)

    def save(self, key, data):
        if hasattr(data, "read"):
            data = data.read()
        if not isinstance(data, bytes):
            data = data.encode()
        self.bucket.upload_bytes(data, key)
        return key

    def read(self, key):
        try:
            downloaded = self.bucket.download_file_by_name(key)
            buf = io.BytesIO()
            downloaded.save(buf)
            return buf.getvalue()
        except Exception as exc:
            if "does not exist" in str(exc).lower():
                return None
            raise

    def delete(self, key):
        try:
            self.bucket.delete_file_version(key)
        except Exception:
            pass


def get_storage():
    """Devuelve el backend adecuado según el entorno."""
    if _env("B2_BUCKET") and _env("B2_KEY_ID") and _env("B2_APPLICATION_KEY"):
        return B2Storage()
    if settings.DEBUG or "test" in sys.argv:
        return LocalStorage()
    raise ImproperlyConfigured(
        "El almacenamiento de grabaciones no está configurado. Definí las "
        "variables B2_KEY_ID, B2_APPLICATION_KEY y B2_BUCKET en producción."
    )