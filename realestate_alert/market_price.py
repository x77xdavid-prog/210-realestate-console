from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from realestate_alert.public_data import (
    Fetcher,
    build_url,
    data_go_kr_key,
    parse_xml_items,
    to_float,
    to_int,
    xml_fetcher,
)

COMMERCIAL_TRADE_URL = (
    "https://apis.data.go.kr/1613000/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade"
)


@dataclass(frozen=True)
class CommercialTrade:
    dong: str
    building_use: str
    zoning: str
    deal_amount_won: int
    building_area_m2: float | None
    land_area_m2: float | None
    floor: str
    build_year: int | None
    deal_date: str
    canceled: bool

    @property
    def price_per_building_m2(self) -> float | None:
        if self.building_area_m2 and self.building_area_m2 > 0:
            return self.deal_amount_won / self.building_area_m2
        return None


@dataclass(frozen=True)
class MarketSummary:
    months: list[str]
    trade_count: int
    avg_price_per_m2: float | None
    min_price_per_m2: float | None
    max_price_per_m2: float | None
    recent_trades: list[CommercialTrade]


def fetch_commercial_trades(
    lawd_cd: str,
    deal_ymd: str,
    service_key: str | None = None,
    fetcher: Fetcher | None = None,
) -> list[CommercialTrade]:
    """국토부 상업업무용 매매 실거래가를 1개월 단위로 조회한다."""
    key = service_key or data_go_kr_key()
    url = build_url(
        COMMERCIAL_TRADE_URL,
        {
            "serviceKey": key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "numOfRows": "1000",
            "pageNo": "1",
        },
    )
    body = (fetcher or xml_fetcher)(url)
    return [_trade_from_item(item) for item in parse_xml_items(body)]


def recent_deal_months(count: int, today: date | None = None) -> list[str]:
    """이번 달부터 거꾸로 count개월의 YYYYMM 목록."""
    current = today or date.today()
    months: list[str] = []
    year, month = current.year, current.month
    for _ in range(count):
        months.append(f"{year}{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return months


def summarize_market(
    lawd_cd: str,
    months: list[str],
    dong: str | None = None,
    service_key: str | None = None,
    fetcher: Fetcher | None = None,
) -> MarketSummary:
    """최근 N개월 실거래를 모아 ㎡당 시세 통계를 만든다."""
    key = service_key or data_go_kr_key()
    trades: list[CommercialTrade] = []
    for deal_ymd in months:
        trades.extend(fetch_commercial_trades(lawd_cd, deal_ymd, key, fetcher))
    valid = [
        trade
        for trade in trades
        if not trade.canceled and (dong is None or dong in trade.dong)
    ]
    prices = [trade.price_per_building_m2 for trade in valid if trade.price_per_building_m2]
    recent = sorted(valid, key=lambda trade: trade.deal_date, reverse=True)[:10]
    return MarketSummary(
        months=months,
        trade_count=len(valid),
        avg_price_per_m2=sum(prices) / len(prices) if prices else None,
        min_price_per_m2=min(prices) if prices else None,
        max_price_per_m2=max(prices) if prices else None,
        recent_trades=recent,
    )


def _trade_from_item(item: dict[str, str]) -> CommercialTrade:
    amount_man_won = to_int(item.get("dealAmount")) or 0
    return CommercialTrade(
        dong=item.get("umdNm", ""),
        building_use=item.get("buildingUse", ""),
        zoning=item.get("landUse", ""),
        deal_amount_won=amount_man_won * 10000,
        building_area_m2=to_float(item.get("buildingAr")),
        land_area_m2=to_float(item.get("plottageAr")),
        floor=item.get("floor", ""),
        build_year=to_int(item.get("buildYear")),
        deal_date=_format_deal_date(item),
        canceled=bool(item.get("cdealType", "").strip()),
    )


def _format_deal_date(item: dict[str, str]) -> str:
    try:
        deal = date(
            int(item.get("dealYear", "")),
            int(item.get("dealMonth", "")),
            int(item.get("dealDay", "")),
        )
    except (TypeError, ValueError):
        return ""
    return deal.isoformat()
