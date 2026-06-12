"""LH 분양임대공고 소스 — 토지·상가 공급 공고를 매물 후보로 가져온다.

data.go.kr '한국토지주택공사_분양임대공고문 조회 서비스' 사용.
공고 단위라 지번 주소는 없고, 상세는 공고문 URL(LH청약플러스)에서 확인한다.
"""

from __future__ import annotations

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
)

LH_NOTICE_URL = "https://apis.data.go.kr/B552555/lhLeaseNoticeInfo1/lhLeaseNoticeInfo1"

# 공고유형: 01 토지, 22 상가 (병원 부지·상가 건물 후보)
DEFAULT_NOTICE_TYPES: tuple[str, ...] = ("01", "22")
# 진행 중인 공고만 (접수마감·정정 제외). 상담요청은 선착순 수의계약 가능 상태라 포함.
ACTIVE_STATUSES: tuple[str, ...] = ("공고중", "접수중", "상담요청")

REGION_CODES = {
    "서울특별시": "11",
    "인천광역시": "28",
    "경기도": "41",
}


@dataclass
class LhNoticeSource:
    """LH 분양임대공고 중 지정 지역의 토지·상가 공고를 매물 소스로 가져온다."""

    sido: str = "서울특별시"
    notice_types: tuple[str, ...] = DEFAULT_NOTICE_TYPES
    service_key: str | None = None
    fetcher: Fetcher | None = None

    def fetch(self) -> list[Listing]:
        try:
            key = self.service_key or data_go_kr_key()
        except MissingApiKeyError as error:
            print(f"[lh] {error} LH 분양공고 소스를 건너뜁니다.")
            return []
        region_code = REGION_CODES.get(self.sido)
        listings: list[Listing] = []
        seen_ids: set[str] = set()
        for notice_type in self.notice_types:
            params = {
                "ServiceKey": key,
                "PG_SZ": "100",
                "PAGE": "1",
                "UPP_AIS_TP_CD": notice_type,
            }
            if region_code:
                params["CNP_CD"] = region_code
            url = build_url(LH_NOTICE_URL, params)
            try:
                payload = parse_json((self.fetcher or json_fetcher)(url))
            except PublicDataError as error:
                print(f"[lh] 조회 실패 (유형 {notice_type}): {error}")
                continue
            for item in _extract_notices(payload):
                listing = _listing_from_notice(item)
                if listing is None or listing.external_id in seen_ids:
                    continue
                seen_ids.add(listing.external_id)
                listings.append(listing)
        return listings


def _extract_notices(payload: Any) -> list[dict[str, Any]]:
    """LH 응답은 [{dsSch:[...]}, {dsList:[...], resHeader:[...]}] 형태의 JSON 배열이다."""
    if not isinstance(payload, list):
        return []
    for part in payload:
        if isinstance(part, dict) and isinstance(part.get("dsList"), list):
            return [item for item in part["dsList"] if isinstance(item, dict)]
    return []


def _listing_from_notice(item: dict[str, Any]) -> Listing | None:
    notice_id = str(item.get("PAN_ID", "")).strip()
    name = str(item.get("PAN_NM", "")).strip()
    status = str(item.get("PAN_SS", "")).strip()
    if not notice_id or not name:
        return None
    if status not in ACTIVE_STATUSES:
        return None
    type_name = str(item.get("UPP_AIS_TP_NM", "")).strip() or "공고"
    region = str(item.get("CNP_CD_NM", "")).strip()
    note_parts = [f"LH 공고 {notice_id}", f"상태 {status}"]
    posted = str(item.get("PAN_NT_ST_DT", "")).strip()
    closing = str(item.get("CLSG_DT", "")).strip()
    if posted:
        note_parts.append(f"게시 {posted}")
    if closing:
        note_parts.append(f"마감 {closing}")
    note_parts.append("상세는 LH청약플러스 공고문에서 확인 (지번·면적·공급가)")
    return Listing(
        source="lh",
        external_id=notice_id,
        title=f"[LH {type_name}] {name}",
        location=region or name,
        deposit=0,
        monthly_rent=0,
        area_m2=0.0,
        floor=None,
        premium=None,
        url=str(item.get("DTL_URL", "")).strip() or "https://apply.lh.or.kr",
        property_type="land" if str(item.get("UPP_AIS_TP_CD", "")) == "01" else "building",
        buildable_note=" · ".join(note_parts),
    )
