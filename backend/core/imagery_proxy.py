from __future__ import annotations

import hashlib
import io
import ipaddress
import math
import socket
import struct
import zlib
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from core.schemas import ImageryScene

PNG_TTL_SECONDS = 86400
MAX_COG_BYTES = 50 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 8.0
MAX_CACHE_ENTRIES = 64
ALLOWED_PREVIEW_HOSTS = {
    'earth-search.aws.element84.com',
    'e84-earth-search-sentinel-data.s3.us-west-2.amazonaws.com',
    'sentinel-cogs.s3.us-west-2.amazonaws.com',
    'sentinel-s2-l2a.s3.amazonaws.com',
}


@dataclass(frozen=True)
class PreviewImage:
    content: bytes
    cache_key: str
    generated_from_source: bool


class UnsafePreviewSourceError(ValueError):
    pass


_MEMORY_CACHE: OrderedDict[str, tuple[datetime, bytes]] = OrderedDict()


def build_preview_cache_headers() -> dict[str, str]:
    return {
        'Cache-Control': 'private, max-age=86400',
        'Vary': 'Authorization',
    }


async def build_preview_png(scene: ImageryScene, bbox: tuple[float, float, float, float], mode: str) -> PreviewImage:
    cache_key = build_cache_key(scene, bbox, mode)
    cached = get_cached_png(cache_key)
    if cached is not None:
        return PreviewImage(content=cached, cache_key=cache_key, generated_from_source=True)

    try:
        source_url = resolve_preview_source(scene, mode)
        if source_url is None:
            return create_placeholder_preview(scene, bbox, mode, cache_key)
        cog_bytes = await fetch_cog_bytes(source_url)
        png = render_cog_preview(cog_bytes, bbox, mode)
    except Exception:
        return create_placeholder_preview(scene, bbox, mode, cache_key)

    set_cached_png(cache_key, png)
    return PreviewImage(content=png, cache_key=cache_key, generated_from_source=True)


async def fetch_cog_bytes(url: str) -> bytes:
    validate_source_url(url)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(FETCH_TIMEOUT_SECONDS, connect=3.0),
        follow_redirects=False,
    ) as client:
        response = await client.get(url, headers={'Range': f'bytes=0-{MAX_COG_BYTES - 1}'})
        response.raise_for_status()
        content = response.content
    if len(content) > MAX_COG_BYTES:
        raise ValueError('COG exceeds max preview size')
    return content


def validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != 'https':
        raise UnsafePreviewSourceError('Preview source must use https')
    host = (parsed.hostname or '').lower()
    if host not in ALLOWED_PREVIEW_HOSTS:
        raise UnsafePreviewSourceError('Preview source host not allowed')
    for _, _, _, _, sockaddr in socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP):
        ip = ipaddress.ip_address(sockaddr[0])
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_reserved, ip.is_multicast, ip.is_unspecified)):
            raise UnsafePreviewSourceError('Preview source resolves to blocked address')


def resolve_preview_source(scene: ImageryScene, mode: str) -> str | None:
    source_url = scene.rgb_url if mode == 'rgb' else scene.ndvi_url
    if not source_url:
        return None
    validate_source_url(source_url)
    return source_url


def render_cog_preview(cog_bytes: bytes, bbox: tuple[float, float, float, float], mode: str) -> bytes:
    try:
        import numpy as np
        import rasterio
        from PIL import Image
        from rasterio.io import MemoryFile
        from rasterio.windows import from_bounds
    except ImportError:
        return placeholder_png('zone', mode)

    with MemoryFile(cog_bytes) as memory_file:
        with memory_file.open() as dataset:
            window = from_bounds(*bbox, transform=dataset.transform).round_offsets().round_lengths()
            if window.width <= 0 or window.height <= 0:
                window = None
            indexes = (1, 2, 3) if mode == 'rgb' and dataset.count >= 3 else 1
            out_shape = (3, 1024, 1024) if indexes == (1, 2, 3) else (1024, 1024)
            data = dataset.read(indexes, window=window, out_shape=out_shape)

    array = np.asarray(data, dtype='float32')
    if array.ndim == 3:
        channels = [normalize_band(array[index]) for index in range(min(array.shape[0], 3))]
        image_array = np.stack(channels, axis=-1).astype('uint8')
    else:
        band = normalize_band(array).astype('uint8')
        image_array = np.stack([band, band, band], axis=-1)

    image = Image.fromarray(image_array, 'RGB').resize((1024, 1024), Image.Resampling.BILINEAR)
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def normalize_band(band):
    import numpy as np

    finite = np.isfinite(band)
    if not finite.any():
        return np.zeros_like(band)
    lower, upper = np.percentile(band[finite], [2, 98])
    if upper <= lower:
        return np.zeros_like(band)
    return np.clip((band - lower) / (upper - lower) * 255, 0, 255)


def create_placeholder_preview(
    scene: ImageryScene,
    bbox: tuple[float, float, float, float],
    mode: str,
    cache_key: str | None = None,
) -> PreviewImage:
    key = cache_key or build_cache_key(scene, bbox, mode)
    png = placeholder_png(scene.zone_id, mode)
    set_cached_png(key, png)
    return PreviewImage(content=png, cache_key=key, generated_from_source=False)


def placeholder_png(zone_id: str, mode: str) -> bytes:
    width = 256
    height = 256
    seed = int(hashlib.sha256(f'{zone_id}:{mode}'.encode()).hexdigest()[:6], 16)
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            wave = int((math.sin((x + seed % 31) / 16) + math.cos((y + seed % 17) / 19) + 2) * 36)
            if mode == 'ndvi':
                row.extend((32, min(255, 90 + wave), 48))
            else:
                row.extend((min(255, 64 + wave), min(255, 96 + wave), min(255, 120 + wave)))
        rows.append(bytes(row))
    return make_png(width, height, b''.join(rows))


def make_png(width: int, height: int, raw: bytes) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', checksum)

    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')


def build_cache_key(scene: ImageryScene, bbox: tuple[float, float, float, float], mode: str) -> str:
    scene_id = scene.scene_id or f'{scene.zone_id}-placeholder'
    bbox_hash = hashlib.sha256(','.join(f'{value:.6f}' for value in bbox).encode()).hexdigest()[:16]
    return f'img_preview:{scene_id}:{mode}:{bbox_hash}'


def prune_cache() -> None:
    now = datetime.now(timezone.utc)
    expired = [key for key, (expires_at, _) in _MEMORY_CACHE.items() if expires_at <= now]
    for key in expired:
        _MEMORY_CACHE.pop(key, None)
    while len(_MEMORY_CACHE) > MAX_CACHE_ENTRIES:
        _MEMORY_CACHE.popitem(last=False)


def get_cached_png(key: str) -> bytes | None:
    prune_cache()
    cached = _MEMORY_CACHE.get(key)
    if cached is None:
        return None
    expires_at, content = cached
    _MEMORY_CACHE.move_to_end(key)
    if expires_at <= datetime.now(timezone.utc):
        _MEMORY_CACHE.pop(key, None)
        return None
    return content


def set_cached_png(key: str, content: bytes) -> None:
    _MEMORY_CACHE[key] = (datetime.now(timezone.utc) + timedelta(seconds=PNG_TTL_SECONDS), content)
    _MEMORY_CACHE.move_to_end(key)
    prune_cache()


def clear_preview_cache() -> None:
    _MEMORY_CACHE.clear()
