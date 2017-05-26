"""
Cloud RAID.
"""

from django.conf import settings


def chunker(f, chunk_size=settings.CLOUDSTRYPE_CHUNK_SIZE):
    """
    Iterator that reads a file-like object and yields a series of chunks.
    """
    while True:
        chunk = f.read(chunk_size)
        if not chunk:
            return
        assert len(chunk) <= chunk_size, 'chunk exceeds %s' % chunk_size
        yield chunk


def raid_chunker(data, chunk, options):
    """
    Prepares chunks necessary to satisfy storage options.
    """
    # TODO: use options to clone chunk, or calculate parity. Yield chunks so
    # caller can store them.
