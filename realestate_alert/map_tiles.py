"""VWorld 지도 타일 서버 프록시 — 카카오맵(JS 키) 반려에 따른 대체 지도.

카카오 JS 키 발급이 반려되어, 별도 키 승인 절차가 없는 한국형 지도로 교체한다.
VWorld(국토교통부 공간정보 오픈플랫폼)는 한글 라벨의 정밀 배경지도를 WMTS
타일로 제공한다. 타일 인증키(VWORLD_API_KEY)는 토지정보 API와 공유하는 민감
키라 브라우저에 노출하지 않고 서버가 대신 받아 중계한다. 키가 없으면 프런트는
키가 필요 없는 OpenStreetMap으로 자연스럽게 폴백한다.

WMTS 타일 좌표는 ``/{z}/{row=y}/{col=x}`` 순서로, Leaflet의 ``{z}/{x}/{y}``와
행·열이 반대다. 프록시는 Leaflet 규약(z, x, y)으로 받아 VWorld 규약으로 바꿔 호출한다.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from typing import Callable

from realestate_alert.public_data import VWORLD_KEY_ENV

VWORLD_TILE_TEMPLATE = "https://api.vworld.kr/req/wmts/1.0.0/{key}/{layer}/{z}/{y}/{x}.png"
VWORLD_DOMAIN_ENV = "VWORLD_DOMAIN"
DEFAULT_REFERER = "http://localhost"
DEFAULT_LAYER = "Base"
MIN_ZOOM, MAX_ZOOM = 6, 19
REQUEST_TIMEOUT_SECONDS = 10
RETRY_STATUSES = frozenset({502, 503, 504})
HTTP_MAX_RETRIES = 1
HTTP_RETRY_BACKOFF_SECONDS = 0.4
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_CACHE_MAX = 256  # 타일 ~40KB × 256 ≈ 10MB. 저사양 클라우드 메모리 한도 내.

# fetcher(url, referer) -> PNG 바이트. 테스트에서 가짜 타일 주입에 사용한다.
TileFetcher = Callable[[str, str], bytes]


class MapTileError(RuntimeError):
    """지도 타일 조회 실패(키 없음·좌표 오류·비정상 응답)."""


_cache: "OrderedDict[str, bytes]" = OrderedDict()
_cache_lock = threading.Lock()


def vworld_tile_key() -> str:
    """타일용 VWorld 키(없으면 빈 문자열). 토지정보 API와 같은 키를 공유한다."""
    return os.environ.get(VWORLD_KEY_ENV, "").strip()


def has_vworld_key() -> bool:
    return bool(vworld_tile_key())


def _referer() -> str:
    """VWorld가 키와 대조하는 Referer. 토지정보 API와 동일한 도메인 설정을 재사용."""
    return os.environ.get(VWORLD_DOMAIN_ENV, "").strip() or DEFAULT_REFERER


def build_vworld_tile_url(z: int, x: int, y: int, key: str, layer: str = DEFAULT_LAYER) -> str:
    return VWORLD_TILE_TEMPLATE.format(key=key, layer=layer, z=z, y=y, x=x)


def _validate_coords(z: int, x: int, y: int) -> None:
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (z, x, y)):
        raise MapTileError("타일 좌표는 정수여야 합니다.")
    if not (MIN_ZOOM <= z <= MAX_ZOOM):
        raise MapTileError(f"지원 줌 범위(z={MIN_ZOOM}~{MAX_ZOOM})를 벗어났습니다: {z}")
    limit = 1 << z
    if not (0 <= x < limit and 0 <= y < limit):
        raise MapTileError(f"타일 좌표 범위를 벗어났습니다: x={x}, y={y} (z={z})")


def _default_fetcher(url: str, referer: str) -> bytes:
    headers = {"User-Agent": "realestate-alert/1.0", "Referer": referer}
    request = urllib.request.Request(url, headers=headers)
    last: Exception | None = None
    for attempt in range(HTTP_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            last = error
            if error.code in RETRY_STATUSES and attempt < HTTP_MAX_RETRIES:
                time.sleep(HTTP_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            break
        except urllib.error.URLError as error:
            last = error
            if attempt < HTTP_MAX_RETRIES:
                time.sleep(HTTP_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            break
    raise MapTileError(f"VWorld 타일 호출 실패: {last}")


def get_map_tile(
    z: int,
    x: int,
    y: int,
    *,
    key: str | None = None,
    layer: str = DEFAULT_LAYER,
    fetcher: TileFetcher | None = None,
    referer: str | None = None,
) -> bytes:
    """Leaflet (z, x, y) 좌표의 VWorld 배경 타일(PNG 바이트)을 반환한다.

    키가 없거나 좌표가 비정상이거나 응답이 PNG가 아니면 ``MapTileError``. 호출부는
    이를 404로 변환해 프런트가 OSM으로 폴백하게 한다. 같은 타일은 메모리에 캐시한다.
    """
    _validate_coords(z, x, y)
    resolved_key = key or vworld_tile_key()
    if not resolved_key:
        raise MapTileError("VWORLD_API_KEY가 설정되지 않았습니다.")

    cache_key = f"{layer}/{z}/{x}/{y}"
    with _cache_lock:
        hit = _cache.get(cache_key)
        if hit is not None:
            _cache.move_to_end(cache_key)
            return hit

    url = build_vworld_tile_url(z, x, y, resolved_key, layer)
    data = (fetcher or _default_fetcher)(url, referer or _referer())
    if not data or not data.startswith(PNG_MAGIC):
        raise MapTileError("VWorld 타일 응답이 PNG가 아닙니다(키/도메인 확인 필요).")

    with _cache_lock:
        _cache[cache_key] = data
        _cache.move_to_end(cache_key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return data


def clear_tile_cache() -> None:
    with _cache_lock:
        _cache.clear()
