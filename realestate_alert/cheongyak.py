"""청약홈 분양정보 — 주변 입주예정 단지 조회 (C3).

병원 입지 분석에서 '주변 입주예정 세대'는 미래 환자 유입을 뜻한다. 한국부동산원
청약홈 APT 분양정보 오픈API(odcloud)로 같은 시군구의 분양 공고를 받아 입주예정
(미래 입주월)만 추린다.

  GET https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail
      ?cond[HSSPLY_ADRES::LIKE]=<시군구>&perPage=100&serviceKey=<키>
  → data[]: HOUSE_NM(단지명) / HSSPLY_ADRES(주소) / SUBSCRPT_AREA_CODE_NM(지역)
            / TOT_SUPLY_HSHLDCO(총세대) / MVN_PREARNGE_YM(입주예정월)
            / RCRIT_PBLANC_DE(공고일) / PBLANC_URL(공고URL) / HOUSE_SECD_NM(구분)

data.go.kr '한국부동산원_청약홈 분양정보 조회 서비스' 활용신청 필요(2026-06-22 승인).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from realestate_alert.public_data import (
    Fetcher,
    MissingApiKeyError,
    PublicDataError,
    build_url,
    data_go_kr_key,
    json_fetcher,
)

APT_SUPPLY_URL = (
    "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"
)


@dataclass(frozen=True)
class SupplyNotice:
    house_name: str
    address: str
    region: str
    total_households: int | None
    move_in_ym: str | None  # 입주예정월 YYYYMM
    notice_date: str  # 모집공고일
    notice_url: str
    house_type: str

    @property
    def move_in_label(self) -> str:
        ym = self.move_in_ym or ""
        return f"{ym[:4]}.{ym[4:6]}" if len(ym) >= 6 else "미정"


def _to_int(value: Any) -> int | None:
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _notice_from_item(item: dict[str, Any]) -> SupplyNotice:
    ym = str(item.get("MVN_PREARNGE_YM") or "").strip()
    return SupplyNotice(
        house_name=str(item.get("HOUSE_NM") or "").strip(),
        address=str(item.get("HSSPLY_ADRES") or "").strip(),
        region=str(item.get("SUBSCRPT_AREA_CODE_NM") or "").strip(),
        total_households=_to_int(item.get("TOT_SUPLY_HSHLDCO")),
        move_in_ym=ym or None,
        notice_date=str(item.get("RCRIT_PBLANC_DE") or "").strip(),
        notice_url=str(item.get("PBLANC_URL") or "").strip(),
        house_type=str(item.get("HOUSE_SECD_NM") or "").strip(),
    )


def fetch_nearby_supply(
    region_keyword: str,
    service_key: str | None = None,
    fetcher: Fetcher | None = None,
    today: date | None = None,
    upcoming_only: bool = True,
) -> list[SupplyNotice]:
    """같은 시군구의 분양 공고 중 입주예정(미래 입주월)만 입주월 오름차순으로."""
    key = service_key or data_go_kr_key()
    params = {
        "page": "1",
        "perPage": "100",
        "cond[HSSPLY_ADRES::LIKE]": region_keyword,
        "serviceKey": key,
    }
    body = (fetcher or json_fetcher)(build_url(APT_SUPPLY_URL, params))
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, TypeError) as error:
        raise PublicDataError(f"청약홈 응답 파싱 실패: {error}") from error

    current_ym = (today or date.today()).strftime("%Y%m")
    notices: list[SupplyNotice] = []
    for item in payload.get("data") or []:
        if not isinstance(item, dict):
            continue
        notice = _notice_from_item(item)
        if not notice.house_name:
            continue
        if upcoming_only and (not notice.move_in_ym or notice.move_in_ym < current_ym):
            continue
        notices.append(notice)
    notices.sort(key=lambda n: n.move_in_ym or "999999")
    return notices


def supply_to_dict(notice: SupplyNotice) -> dict[str, Any]:
    return {
        "house_name": notice.house_name,
        "address": notice.address,
        "region": notice.region,
        "total_households": notice.total_households,
        "move_in_ym": notice.move_in_ym,
        "move_in_label": notice.move_in_label,
        "notice_date": notice.notice_date,
        "notice_url": notice.notice_url,
        "house_type": notice.house_type,
    }


def nearby_supply_report(
    region_keyword: str, today: date | None = None, fetcher: Fetcher | None = None
) -> dict[str, Any]:
    """엔드포인트용 — 실패(키 없음/조회 실패)는 흡수하고 error에 사유를 남긴다."""
    result: dict[str, Any] = {"region": region_keyword, "supplies": [], "error": None}
    if not region_keyword:
        result["error"] = "지역 정보가 없습니다."
        return result
    try:
        notices = fetch_nearby_supply(region_keyword, fetcher=fetcher, today=today)
        result["supplies"] = [supply_to_dict(n) for n in notices]
    except (MissingApiKeyError, PublicDataError) as error:
        result["error"] = str(error)
    return result
