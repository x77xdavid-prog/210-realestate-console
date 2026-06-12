from __future__ import annotations

from urllib.parse import quote


def naver_land_url(location: str) -> str:
    """네이버 부동산 통합 검색 URL을 생성한다 (좌표가 없을 때의 차선책)."""
    return f"https://new.land.naver.com/search?query={quote(location)}"


def naver_land_coord_url(latitude: float, longitude: float, zoom: int = 17) -> str:
    """좌표 중심으로 네이버 부동산 지도를 여는 URL. query 방식보다 정확하다."""
    return f"https://new.land.naver.com/search?ms={latitude},{longitude},{zoom}&e=RETAIL"


def naver_map_url(location: str) -> str:
    """네이버 지도 주소 검색 URL을 생성한다."""
    return f"https://map.naver.com/p/search/{quote(location)}"
