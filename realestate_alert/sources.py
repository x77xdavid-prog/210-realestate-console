from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from realestate_alert.models import Listing


class ListingSource(Protocol):
    def fetch(self) -> list[Listing]:
        raise NotImplementedError


class JsonFileSource:
    def __init__(self, path: Path):
        self.path = path

    def fetch(self) -> list[Listing]:
        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            raise ValueError(f"JSON source must contain a list: {self.path}")
        return [_listing_from_dict(item, default_source=self.path.stem) for item in data]


def _listing_from_dict(data: dict, default_source: str) -> Listing:
    return Listing(
        source=str(data.get("source") or default_source),
        external_id=str(data["external_id"]),
        title=str(data["title"]),
        location=str(data["location"]),
        deposit=int(data["deposit"]),
        monthly_rent=int(data["monthly_rent"]),
        area_m2=float(data["area_m2"]),
        floor=None if data.get("floor") is None else str(data.get("floor")),
        premium=None if data.get("premium") is None else int(data.get("premium")),
        url=str(data["url"]),
        property_type=None if data.get("property_type") is None else str(data.get("property_type")),
        usage=None if data.get("usage") is None else str(data.get("usage")),
        land_area_m2=_optional_float(data.get("land_area_m2")),
        building_area_m2=_optional_float(data.get("building_area_m2")),
        floors_total=_optional_int(data.get("floors_total")),
        parking_spaces=_optional_int(data.get("parking_spaces")),
        zoning=None if data.get("zoning") is None else str(data.get("zoning")),
        road_access=None if data.get("road_access") is None else str(data.get("road_access")),
        building_coverage_ratio=_optional_float(data.get("building_coverage_ratio")),
        floor_area_ratio=_optional_float(data.get("floor_area_ratio")),
        approval_year=_optional_int(data.get("approval_year")),
        elevator=None if data.get("elevator") is None else bool(data.get("elevator")),
        buildable_note=None if data.get("buildable_note") is None else str(data.get("buildable_note")),
        appraisal_price=_optional_int(data.get("appraisal_price")),
        min_bid_price=_optional_int(data.get("min_bid_price")),
        fail_count=_optional_int(data.get("fail_count")),
        sale_date=None if data.get("sale_date") is None else str(data.get("sale_date")),
        bid_begin=None if data.get("bid_begin") is None else str(data.get("bid_begin")),
        bid_end=None if data.get("bid_end") is None else str(data.get("bid_end")),
    )


def _optional_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value:
            return None
    return float(value)


def _optional_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value:
            return None
    return int(value)
