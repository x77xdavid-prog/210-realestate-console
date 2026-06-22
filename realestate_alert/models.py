from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Listing:
    source: str
    external_id: str
    title: str
    location: str
    deposit: int
    monthly_rent: int
    area_m2: float
    floor: str | None
    premium: int | None
    url: str
    property_type: str | None = None
    usage: str | None = None
    appraisal_price: int | None = None
    min_bid_price: int | None = None
    fail_count: int | None = None
    sale_date: str | None = None
    land_area_m2: float | None = None
    building_area_m2: float | None = None
    floors_total: int | None = None
    parking_spaces: int | None = None
    zoning: str | None = None
    road_access: str | None = None
    building_coverage_ratio: float | None = None
    floor_area_ratio: float | None = None
    approval_year: int | None = None
    elevator: bool | None = None
    buildable_note: str | None = None
    thumbnail_path: str | None = None
    photo_count: int | None = None
    incumbrance_tags: tuple[str, ...] = ()
    cs_no: str | None = None
    cort_ofc_cd: str | None = None
    gds_seq: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    @property
    def identity(self) -> str:
        return f"{self.source}:{self.external_id}"

    def searchable_text(self) -> str:
        parts = [self.title, self.location, self.floor or "", self.url]
        return " ".join(parts).lower()

    def contains_any(self, keywords: list[str]) -> bool:
        text = self.searchable_text()
        return any(keyword.lower() in text for keyword in keywords)


@dataclass(frozen=True)
class SearchCriteria:
    locations: list[str] = field(default_factory=list)
    max_deposit: int | None = None
    max_monthly_rent: int | None = None
    min_area_m2: float | None = None
    max_premium: int | None = None
    required_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Photo:
    file: str          # 로컬 상대경로 (web_server가 서빙)
    dvs: str           # 사진 구분 라벨
    seq: int


@dataclass(frozen=True)
class StatusItem:
    label: str         # 현황 요항 라벨
    text: str


@dataclass(frozen=True)
class BidEvent:
    date: str          # YYYYMMDD
    low: int | None    # 해당 회차 최저가
    result: str        # 유찰 / 진행 / 매각결정 / 변경


@dataclass(frozen=True)
class AuctionDetail:
    identity: str
    court: str
    dept: str
    case_no: str
    addr_road: str
    addr_jibun: str
    usage: str
    auction_type: str
    land_m2: float | None
    bldg_m2: float | None
    appraisal: int | None
    min_bid: int | None
    deposit: int | None
    claim_amt: int | None
    fail_count: int | None
    sale_date: str | None
    photos: tuple[Photo, ...] = ()
    status_items: tuple[StatusItem, ...] = ()
    bid_history: tuple[BidEvent, ...] = ()
    incumbrances: tuple[str, ...] = ()
    doc_ecid: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    presented_outside: tuple[dict, ...] = ()
    building_detail: tuple[dict, ...] = ()
    jibun_list: tuple[dict, ...] = ()
    dividend_deadline: str | None = None
    sale_notice: str | None = None
