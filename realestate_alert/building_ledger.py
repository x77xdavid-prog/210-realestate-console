from __future__ import annotations

from dataclasses import dataclass

from realestate_alert.address import ParcelAddress
from realestate_alert.public_data import (
    Fetcher,
    build_url,
    data_go_kr_key,
    parse_xml_items,
    to_float,
    to_int,
    xml_fetcher,
)

TITLE_INFO_URL = "https://apis.data.go.kr/1613000/BldRgstHubService/getBrTitleInfo"

_PARKING_COUNT_FIELDS = (
    "indrMechUtcnt",
    "oudrMechUtcnt",
    "indrAutoUtcnt",
    "oudrAutoUtcnt",
)


@dataclass(frozen=True)
class BuildingTitle:
    building_name: str
    main_purpose: str
    plat_area_m2: float | None
    arch_area_m2: float | None
    total_area_m2: float | None
    building_coverage_ratio: float | None
    floor_area_ratio: float | None
    ground_floors: int | None
    underground_floors: int | None
    parking_spaces: int | None
    elevator_count: int | None
    approval_date: str | None

    @property
    def approval_year(self) -> int | None:
        if self.approval_date and len(self.approval_date) >= 4 and self.approval_date[:4].isdigit():
            return int(self.approval_date[:4])
        return None

    @property
    def has_elevator(self) -> bool | None:
        if self.elevator_count is None:
            return None
        return self.elevator_count > 0


def fetch_building_titles(
    parcel: ParcelAddress,
    service_key: str | None = None,
    fetcher: Fetcher | None = None,
) -> list[BuildingTitle]:
    """건축HUB 건축물대장 표제부를 조회한다 (같은 필지에 여러 동이 있을 수 있다)."""
    key = service_key or data_go_kr_key()
    url = build_url(
        TITLE_INFO_URL,
        {
            "serviceKey": key,
            "sigunguCd": parcel.sigungu_code,
            "bjdongCd": parcel.bjdong_code,
            "platGbCd": parcel.plat_gb_cd,
            "bun": parcel.bun_padded,
            "ji": parcel.ji_padded,
            "numOfRows": "30",
            "pageNo": "1",
        },
    )
    body = (fetcher or xml_fetcher)(url)
    return [_title_from_item(item) for item in parse_xml_items(body)]


def _parking_count(item: dict[str, str], field: str) -> int | None:
    """필드가 아예 없으면 None, 있는데 비어 있으면 0으로 본다 (대장의 빈 값은 0대 의미)."""
    if field not in item:
        return None
    raw = item[field].strip()
    if not raw:
        return 0
    return to_int(raw)


def _title_from_item(item: dict[str, str]) -> BuildingTitle:
    parking_counts = [_parking_count(item, field) for field in _PARKING_COUNT_FIELDS]
    known_counts = [count for count in parking_counts if count is not None]
    elevator_ride = to_int(item.get("rideUseElvtCnt"))
    elevator_emergency = to_int(item.get("emgenUseElvtCnt"))
    elevator_total = None
    if elevator_ride is not None or elevator_emergency is not None:
        elevator_total = (elevator_ride or 0) + (elevator_emergency or 0)
    return BuildingTitle(
        building_name=item.get("bldNm", ""),
        main_purpose=item.get("mainPurpsCdNm", ""),
        plat_area_m2=to_float(item.get("platArea")),
        arch_area_m2=to_float(item.get("archArea")),
        total_area_m2=to_float(item.get("totArea")),
        building_coverage_ratio=to_float(item.get("bcRat")),
        floor_area_ratio=to_float(item.get("vlRat")),
        ground_floors=to_int(item.get("grndFlrCnt")),
        underground_floors=to_int(item.get("ugrndFlrCnt")),
        parking_spaces=sum(known_counts) if known_counts else None,
        elevator_count=elevator_total,
        approval_date=item.get("useAprDay") or None,
    )


def primary_title(titles: list[BuildingTitle]) -> BuildingTitle | None:
    """복수 동이면 연면적이 가장 큰 동(주 건물)을 대표로 사용한다."""
    if not titles:
        return None
    return max(titles, key=lambda title: title.total_area_m2 or 0)
