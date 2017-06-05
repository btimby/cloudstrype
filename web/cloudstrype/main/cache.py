import os
import pickle
import tempfile

from django.core.cache.backends.filebased import FileBasedCache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.core.files.move import file_move_safe


class ChunkFileCache(FileBasedCache):
    """
    Caches to filesystem without processing.

    Chunks are already compressed and encrypted. No pickling necessary.
    """

    def get(self, key, default=None, version=None):
        fname = self._key_to_file(key, version)
        try:
            with open(fname, 'rb') as f:
                if not self._is_expired(f):
                    return f.read()
        except FileNotFoundError:
            pass
        return default

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None):
        self._createdir()
        fname = self._key_to_file(key, version)
        self._cull()
        fd, tmp_path = tempfile.mkstemp(dir=self._dir)
        renamed = False
        try:
            with open(fd, 'wb') as f:
                expiry = self.get_backend_timeout(timeout)
                f.write(pickle.dumps(expiry, pickle.HIGHEST_PROTOCOL))
                f.write(value)
            file_move_safe(tmp_path, fname, allow_overwrite=True)
            renamed = True
        finally:
            if not renamed:
                os.remove(tmp_path)
