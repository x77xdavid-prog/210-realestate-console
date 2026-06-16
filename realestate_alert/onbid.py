from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from realestate_alert.models import Listing
from realestate_alert.public_data import (
    Fetcher,
    MissingApiKeyError,
    PublicDataError,
    build_url,
    data_go_kr_key,
    json_fetcher,
    parse_json,
    to_float,
    to_int,
)

# 차세대 온비드 부동산 물건목록 조회 (data.go.kr 15157207)
ONBID_LIST_URL = "https://apis.data.go.kr/B010003/OnbidRlstListSrvc2/getRlstCltrList2"
ONBID_PORTAL_URL = "https://www.onbid.co.kr"

# 재산유형: 0007 압류재산, 0010 국유재산, 0005 기타일반재산, 0006 유입재산, 0008 수탁재산
DEFAULT_PROPERTY_DIVISIONS = "0007,0010,0005,0006,0008"
SALE_METHOD_CD = "0001"  # 매각

# 물건명 앞부분의 지번 주소 (예: "서울특별시 양천구 목동 324-18 진우힐 ...")
_PARCEL_IN_NAME = re.compile(
    r"(?P<addr>\S+(?:특별시|광역시|특별자치시|특별자치도|도)\s+\S+[시군구]"
    r"(?:\s+\S+[시군구])?\s+\S+(?:동|가|리|읍|면)\s+(?:산\s*)?\d+(?:-\d+)?)"
)


def _first_int(text: str) -> int | None:
    """문자열에서 첫 숫자(쉼표 포함)를 정수로 추출한다. 예: '최저 1,000,000원' → 1000000."""
    match = re.search(r"[\d,]{2,}", text or "")
    if not match:
        return None
    digits = match.group().replace(",", "")
    return int(digits) if digits.isdigit() else None


@dataclass
class OnbidSource:
    """온비드 공매 중 지정 지역의 매각 물건을 매물 소스로 가져온다."""

    sido: str = "서울특별시"
    sigungu: str = "양천구"
    property_divisions: str = DEFAULT_PROPERTY_DIVISIONS
    service_key: str | None = None
    fetcher: Fetcher | None = None

    def fetch(self) -> list[Listing]:
        try:
            key = self.service_key or data_go_kr_key()
        except MissingApiKeyError as error:
            print(f"[onbid] {error} 온비드 공매 소스를 건너뜁니다.")
            return []
        url = build_url(
            ONBID_LIST_URL,
            {
                "serviceKey": key,
                "pageNo": "1",
                "numOfRows": "100",
                "resultType": "json",
                "prptDivCd": self.property_divisions,
                "pvctTrgtYn": "N",
                "dspsMthodCd": SALE_METHOD_CD,
                "lctnSdnm": self.sido,
                "lctnSggnm": self.sigungu,
            },
        )
        try:
            payload = parse_json((self.fetcher or json_fetcher)(url))
        except PublicDataError as error:
            print(f"[onbid] 조회 실패: {error}")
            return []
        # 같은 물건이 입찰 회차(공매조건)별로 여러 행으로 오므로 물건관리번호 기준 첫 행만 사용한다.
        listings: list[Listing] = []
        seen_ids: set[str] = set()
        for item in _extract_items(payload):
            listing = _listing_from_item(item)
            if listing is None or listing.external_id in seen_ids:
                continue
            seen_ids.add(listing.external_id)
            listings.append(listing)
        return listings


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    body = payload.get("body") or {}
    items = body.get("items") or {}
    raw = items.get("item") if isinstance(items, dict) else items
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _listing_from_item(item: dict[str, Any]) -> Listing | None:
    management_no = str(item.get("cltrMngNo", "")).strip()
    name = str(item.get("onbidCltrNm", "")).strip()
    if not management_no or not name:
        return None
    # 네이버 부동산/지도가 필지 단위로 열리도록 물건명에서 지번 주소를 우선 추출한다.
    parcel_match = _PARCEL_IN_NAME.search(name)
    location = parcel_match.group("addr") if parcel_match else " ".join(
        part
        for part in (
            str(item.get("lctnSdnm", "")).strip(),
            str(item.get("lctnSggnm", "")).strip(),
            str(item.get("lctnEmdNm", "")).strip(),
        )
        if part
    )
    usage = str(item.get("cltrUsgMclsCtgrNm", "") or item.get("cltrUsgLclsCtgrNm", "")).strip()
    building_area = to_float(str(item.get("bldSqms", "")))
    land_area = to_float(str(item.get("landSqms", "")))
    note_parts = [f"공매 물건관리번호 {management_no}"]
    appraisal = to_int(str(item.get("apslEvlAmt", "")))
    if appraisal:
        note_parts.append(f"감정가 {appraisal:,}원")
    lowest_bid = str(item.get("lowstBidPrcIndctCont", "")).strip()
    if lowest_bid:
        note_parts.append(f"최저입찰 {lowest_bid}")
    status = str(item.get("pbctStatNm", "")).strip()
    if status:
        note_parts.append(f"상태 {status}")
    begin = str(item.get("cltrBidBgngDt", "")).strip()
    end = str(item.get("cltrBidEndDt", "")).strip()
    if begin or end:
        note_parts.append(f"입찰 {begin}~{end}")
    note_parts.append("온비드(onbid.co.kr)에서 물건관리번호로 검색")
    return Listing(
        source="onbid",
        external_id=management_no,
        title=f"[공매] {name}" + (f" ({usage})" if usage else ""),
        location=location or name,
        deposit=0,
        monthly_rent=0,
        area_m2=building_area or land_area or 0.0,
        floor=None,
        premium=None,
        url=ONBID_PORTAL_URL,
        property_type="land" if (building_area or 0) == 0 else "building",
        usage=usage or None,
        appraisal_price=appraisal or None,
        min_bid_price=_first_int(lowest_bid),
        sale_date=end[:8] if len(end) >= 8 else None,
        land_area_m2=land_area,
        building_area_m2=building_area,
        buildable_note=" · ".join(note_parts),
    )
