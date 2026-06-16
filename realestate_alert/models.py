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
