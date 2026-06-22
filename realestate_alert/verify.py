from __future__ import annotations

from dataclasses import replace
from typing import Any

from realestate_alert.address import ParcelAddress, extract_dong, parse_parcel_address
from realestate_alert.building_ledger import BuildingTitle, fetch_building_titles, primary_title
from realestate_alert.land_info import LandSummary, fetch_land_summary, geocode_region_code
from realestate_alert.market_price import MarketSummary, recent_deal_months, summarize_market
from realestate_alert.models import Listing
from realestate_alert.public_data import Fetcher, MissingApiKeyError, PublicDataError

DEFAULT_MARKET_MONTHS = 6


def verify_address(
    address: str,
    market_months: int = DEFAULT_MARKET_MONTHS,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    """주소 하나에 대해 건축물대장 + 토지정보 + 실거래 시세를 종합한 검증 리포트를 만든다.

    API 키가 없는 소스는 건너뛰고 리포트에 발급 안내를 남긴다.
    """
    report: dict[str, Any] = {
        "address": address,
        "parcel": None,
        "building": None,
        "land": None,
        "market": None,
        "errors": {},
    }
    try:
        parcel = parse_parcel_address(address)
    except ValueError as error:
        report["errors"]["address"] = str(error)
        return report
    report["parcel"] = {
        "sigungu": parcel.sigungu,
        "dong": parcel.dong,
        "bun": parcel.bun,
        "ji": parcel.ji,
        "pnu": parcel.pnu,
        "sigungu_code": parcel.sigungu_code,
        "bjdong_code": parcel.bjdong_code,
    }

    building = _try_building(parcel, report, fetcher)
    if building is not None:
        report["building"] = _building_to_dict(building)

    land = _try_land(parcel, report, fetcher)
    if land is not None:
        report["land"] = _land_to_dict(land)

    market = _try_market(parcel, market_months, report, fetcher)
    if market is not None:
        report["market"] = _market_to_dict(market)

    return report


def market_for_address(
    address: str,
    market_months: int = DEFAULT_MARKET_MONTHS,
    fetcher: Fetcher | None = None,
) -> dict[str, Any]:
    """주소 하나에 대해 실거래 시세만 조회한다 (건축물대장/토지 호출 없음).

    상세 페이지 시세분석 탭이 가볍게 시세만 받기 위한 헬퍼.
    주소 파싱 실패·API 키 없음·조회 실패는 모두 흡수하고 ``error``에 사유를 남긴다.
    """
    result: dict[str, Any] = {"address": address, "market": None, "error": None}
    lawd_cd, dong = _resolve_market_region(address, fetcher)
    if not lawd_cd:
        result["error"] = f"지역 코드를 확인할 수 없습니다: {address}"
        return result
    try:
        market = summarize_market(
            lawd_cd=lawd_cd,
            months=recent_deal_months(market_months),
            dong=dong,
            fetcher=fetcher,
        )
    except (MissingApiKeyError, PublicDataError) as error:
        result["error"] = str(error)
        return result
    result["market"] = _market_to_dict(market)
    return result


def _resolve_market_region(
    address: str, fetcher: Fetcher | None
) -> tuple[str | None, str | None]:
    """주소 → (시군구 lawd_cd 5자리, 법정동명). 하드코딩 테이블 우선, 없으면 VWorld 보강.

    테이블(관악/양천)은 외부호출 없이 빠르고, 그 외 전국은 VWorld 지오코더의
    법정동코드(level4LC) 앞 5자리로 시군구 코드를 얻는다. dong은 시세 필터용 법정동명.
    """
    try:
        parcel = parse_parcel_address(address)
        return parcel.sigungu_code, parcel.dong
    except ValueError:
        pass
    try:
        code = geocode_region_code(address, fetcher=fetcher)
    except (MissingApiKeyError, PublicDataError):
        code = None
    lawd_cd = code[:5] if code and len(code) >= 5 else None
    return lawd_cd, extract_dong(address)


def enrich_listing(
    listing: Listing,
    building: BuildingTitle | None,
    land: LandSummary | None,
) -> Listing:
    """공공 데이터로 매물의 비어 있는 필드만 채운다 (기존 값은 보존)."""
    updates: dict[str, Any] = {}
    if building is not None:
        _fill(updates, listing, "land_area_m2", building.plat_area_m2)
        _fill(updates, listing, "building_area_m2", building.total_area_m2)
        _fill(updates, listing, "floors_total", building.ground_floors)
        _fill(updates, listing, "parking_spaces", building.parking_spaces)
        _fill(updates, listing, "building_coverage_ratio", building.building_coverage_ratio)
        _fill(updates, listing, "floor_area_ratio", building.floor_area_ratio)
        _fill(updates, listing, "approval_year", building.approval_year)
        _fill(updates, listing, "elevator", building.has_elevator)
    if land is not None:
        if land.zoning_names:
            _fill(updates, listing, "zoning", ", ".join(land.zoning_names))
        if land.road_side:
            hint = f" (약 {land.road_width_hint_m:g}m급)" if land.road_width_hint_m else ""
            _fill(updates, listing, "road_access", f"{land.road_side}{hint}")
    if not updates:
        return listing
    return replace(listing, **updates)


def _fill(updates: dict[str, Any], listing: Listing, field_name: str, value: Any) -> None:
    if value is None:
        return
    if getattr(listing, field_name) is None:
        updates[field_name] = value


def _try_building(
    parcel: ParcelAddress, report: dict[str, Any], fetcher: Fetcher | None
) -> BuildingTitle | None:
    try:
        return primary_title(fetch_building_titles(parcel, fetcher=fetcher))
    except (MissingApiKeyError, PublicDataError) as error:
        report["errors"]["building"] = str(error)
        return None


def _try_land(
    parcel: ParcelAddress, report: dict[str, Any], fetcher: Fetcher | None
) -> LandSummary | None:
    try:
        return fetch_land_summary(parcel.pnu, fetcher=fetcher)
    except (MissingApiKeyError, PublicDataError) as error:
        report["errors"]["land"] = str(error)
        return None


def _try_market(
    parcel: ParcelAddress, months: int, report: dict[str, Any], fetcher: Fetcher | None
) -> MarketSummary | None:
    try:
        return summarize_market(
            lawd_cd=parcel.sigungu_code,
            months=recent_deal_months(months),
            dong=parcel.dong,
            fetcher=fetcher,
        )
    except (MissingApiKeyError, PublicDataError) as error:
        report["errors"]["market"] = str(error)
        return None


def _building_to_dict(building: BuildingTitle) -> dict[str, Any]:
    return {
        "building_name": building.building_name,
        "main_purpose": building.main_purpose,
        "plat_area_m2": building.plat_area_m2,
        "arch_area_m2": building.arch_area_m2,
        "total_area_m2": building.total_area_m2,
        "building_coverage_ratio": building.building_coverage_ratio,
        "floor_area_ratio": building.floor_area_ratio,
        "ground_floors": building.ground_floors,
        "underground_floors": building.underground_floors,
        "parking_spaces": building.parking_spaces,
        "elevator_count": building.elevator_count,
        "approval_date": building.approval_date,
        "approval_year": building.approval_year,
    }


def _land_to_dict(land: LandSummary) -> dict[str, Any]:
    return {
        "zoning_names": land.zoning_names,
        "road_side": land.road_side,
        "road_width_hint_m": land.road_width_hint_m,
        "land_use_situation": land.land_use_situation,
        "terrain_height": land.terrain_height,
        "terrain_shape": land.terrain_shape,
        "official_price_per_m2": land.official_price_per_m2,
        "official_price_year": land.official_price_year,
    }


def _market_to_dict(market: MarketSummary) -> dict[str, Any]:
    return {
        "months": market.months,
        "trade_count": market.trade_count,
        "avg_price_per_m2": market.avg_price_per_m2,
        "min_price_per_m2": market.min_price_per_m2,
        "max_price_per_m2": market.max_price_per_m2,
        "recent_trades": [
            {
                "dong": trade.dong,
                "building_use": trade.building_use,
                "zoning": trade.zoning,
                "deal_amount_won": trade.deal_amount_won,
                "building_area_m2": trade.building_area_m2,
                "land_area_m2": trade.land_area_m2,
                "floor": trade.floor,
                "build_year": trade.build_year,
                "deal_date": trade.deal_date,
                "price_per_building_m2": trade.price_per_building_m2,
            }
            for trade in market.recent_trades
        ],
    }
