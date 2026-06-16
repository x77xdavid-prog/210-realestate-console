from __future__ import annotations

import os
from dataclasses import dataclass, field

from realestate_alert.public_data import (
    Fetcher,
    build_url,
    find_dicts_with_key,
    http_get,
    parse_json,
    to_float,
    vworld_key,
)

LAND_USE_URL = "https://api.vworld.kr/ned/data/getLandUseAttr"
LAND_CHARACTERISTICS_URL = "https://api.vworld.kr/ned/data/getLandCharacteristics"
LAND_PRICE_URL = "https://api.vworld.kr/ned/data/getIndvdLandPriceAttr"
GEOCODE_URL = "https://api.vworld.kr/req/address"

# 주소 → 좌표 캐시 (지오코딩 일 40,000건 제한 보호 + 응답 속도)
_geocode_cache: dict[str, tuple[float, float] | None] = {}

VWORLD_DOMAIN_ENV = "VWORLD_DOMAIN"
DEFAULT_VWORLD_DOMAIN = "http://localhost"


def _vworld_domain() -> str:
    """V-World 키 발급 시 등록한 도메인. domain 파라미터가 없으면 INCORRECT_KEY 응답이 온다."""
    return os.environ.get(VWORLD_DOMAIN_ENV, DEFAULT_VWORLD_DOMAIN)

# 토지특성 도로접면 분류 → 추정 접도 폭(m). 정밀 폭은 도로대장 확인 필요.
# 실제 표기 예: 광대한면, 중로각지, 소로한면, 세로한면(가), 세로각지(불), 맹지
ROAD_SIDE_WIDTH_HINTS = {
    "광대": 25.0,
    "중로": 12.0,
    "소로": 8.0,
}


@dataclass(frozen=True)
class LandSummary:
    zoning_names: list[str] = field(default_factory=list)
    road_side: str | None = None
    road_width_hint_m: float | None = None
    land_use_situation: str | None = None
    terrain_height: str | None = None
    terrain_shape: str | None = None
    official_price_per_m2: float | None = None
    official_price_year: str | None = None


def fetch_land_use_names(pnu: str, key: str | None = None, fetcher: Fetcher | None = None) -> list[str]:
    """토지이용계획 속성에서 '포함' 용도지역지구명 목록을 가져온다."""
    url = build_url(
        LAND_USE_URL,
        {
            "pnu": pnu,
            "key": key or vworld_key(),
            "domain": _vworld_domain(),
            "format": "json",
            "numOfRows": "100",
            "pageNo": "1",
        },
    )
    payload = parse_json((fetcher or http_get)(url))
    names: list[str] = []
    for item in find_dicts_with_key(payload, "prposAreaDstrcCodeNm"):
        name = str(item.get("prposAreaDstrcCodeNm", "")).strip()
        conflict = str(item.get("cnflcAtNm", "")).strip()
        if name and conflict != "저촉":
            names.append(name)
    # 순서 보존 중복 제거
    return list(dict.fromkeys(names))


def fetch_land_characteristics(
    pnu: str, key: str | None = None, fetcher: Fetcher | None = None
) -> dict[str, str]:
    url = build_url(
        LAND_CHARACTERISTICS_URL,
        {
            "pnu": pnu,
            "key": key or vworld_key(),
            "domain": _vworld_domain(),
            "format": "json",
            "numOfRows": "10",
            "pageNo": "1",
        },
    )
    payload = parse_json((fetcher or http_get)(url))
    items = find_dicts_with_key(payload, "roadSideCodeNm")
    if not items:
        return {}
    # 기준연도 최신 항목 사용
    latest = max(items, key=lambda item: str(item.get("stdrYear", "")))
    return {key_: str(value) for key_, value in latest.items()}


def fetch_official_land_price(
    pnu: str, key: str | None = None, fetcher: Fetcher | None = None
) -> tuple[float | None, str | None]:
    """최신 기준연도의 개별공시지가(원/㎡)를 반환한다."""
    url = build_url(
        LAND_PRICE_URL,
        {
            "pnu": pnu,
            "key": key or vworld_key(),
            "domain": _vworld_domain(),
            "format": "json",
            "numOfRows": "100",
            "pageNo": "1",
        },
    )
    payload = parse_json((fetcher or http_get)(url))
    items = find_dicts_with_key(payload, "pblntfPclnd")
    if not items:
        return None, None
    latest = max(items, key=lambda item: str(item.get("stdrYear", "")))
    return to_float(str(latest.get("pblntfPclnd", ""))), str(latest.get("stdrYear", "")) or None


def cached_coords(address: str) -> tuple[float, float] | None:
    """이미 변환된 좌표만 반환한다(네트워크 호출 없음). 캐시에 없으면 None.

    HTTP 요청 경로에서 동기 지오코딩으로 응답이 지연/502되는 것을 막기 위해,
    좌표는 백그라운드 수집 때 미리 변환(캐시 워밍)하고 응답은 캐시만 읽는다.
    """
    return _geocode_cache.get(address)


def geocode_parcel(
    address: str, key: str | None = None, fetcher: Fetcher | None = None
) -> tuple[float, float] | None:
    """지번 주소를 (위도, 경도)로 변환한다. 실패하면 None (결과는 캐시됨)."""
    if address in _geocode_cache:
        return _geocode_cache[address]
    url = build_url(
        GEOCODE_URL,
        {
            "service": "address",
            "request": "getCoord",
            "version": "2.0",
            "address": address,
            "type": "PARCEL",
            "key": key or vworld_key(),
            "domain": _vworld_domain(),
            "format": "json",
        },
    )
    payload = parse_json((fetcher or http_get)(url))
    points = find_dicts_with_key(payload, "y")
    coords: tuple[float, float] | None = None
    for point in points:
        latitude = to_float(str(point.get("y", "")))
        longitude = to_float(str(point.get("x", "")))
        if latitude is not None and longitude is not None:
            coords = (latitude, longitude)
            break
    _geocode_cache[address] = coords
    return coords


def road_width_hint(road_side: str | None) -> float | None:
    if not road_side:
        return None
    if "맹지" in road_side:
        return 0.0
    if "세로" in road_side:
        return 3.0 if "불" in road_side else 4.0
    for keyword, width in ROAD_SIDE_WIDTH_HINTS.items():
        if keyword in road_side:
            return width
    return None


def fetch_land_summary(pnu: str, key: str | None = None, fetcher: Fetcher | None = None) -> LandSummary:
    resolved_key = key or vworld_key()
    zoning_names = fetch_land_use_names(pnu, resolved_key, fetcher)
    characteristics = fetch_land_characteristics(pnu, resolved_key, fetcher)
    price, price_year = fetch_official_land_price(pnu, resolved_key, fetcher)
    road_side = characteristics.get("roadSideCodeNm")
    return LandSummary(
        zoning_names=zoning_names,
        road_side=road_side,
        road_width_hint_m=road_width_hint(road_side),
        land_use_situation=characteristics.get("ladUseSittnNm"),
        terrain_height=characteristics.get("tpgrphHgCodeNm"),
        terrain_shape=characteristics.get("tpgrphFrmCodeNm"),
        official_price_per_m2=price,
        official_price_year=price_year,
    )
