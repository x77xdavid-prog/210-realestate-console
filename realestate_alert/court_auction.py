"""법원경매 소스 — 대법원 법원경매정보(courtauction.go.kr) 검색 API를 직접 호출한다.

공식 오픈API가 없어 사이트의 내부 검색 엔드포인트를 사용한다.
사이트 개편 시 파라미터·필드명이 바뀔 수 있으므로 실패는 빈 목록으로 흡수한다.
세션 쿠키가 필요해 index 페이지를 먼저 호출한 뒤 검색한다.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar
from typing import Any, Callable

from realestate_alert.models import Listing

BASE_URL = "https://www.courtauction.go.kr"
INDEX_URL = f"{BASE_URL}/pgj/index.on"
SEARCH_URL = f"{BASE_URL}/pgj/pgjsearch/searchControllerMain.on"
SEARCH_REFERER = f"{BASE_URL}/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT_SECONDS = 20
SEARCH_WINDOW_DAYS = 28
MAX_PAGE_SIZE = 40  # 사이트가 허용하는 최대 페이지 크기 (100은 400 거부)
MAX_PAGES = 20  # 안전 상한 — 한 법원 관할이 이보다 많으면 잘릴 수 있음

# 법원명 → 법원코드 (필요 지역만; 양천·강서·구로·영등포는 서울남부지법 관할)
COURT_CODES = {
    "서울중앙지방법원": "B000210",
    "서울동부지방법원": "B000211",
    "서울서부지방법원": "B000215",
    "서울남부지방법원": "B000212",
    "서울북부지방법원": "B000213",
}

# 검색 본문에 body(dict)를 받아 JSON 문자열을 돌려주는 함수 (테스트 주입용)
SearchFetcher = Callable[[dict[str, Any]], str]


def build_search_body(
    court_code: str,
    begin_ymd: str,
    end_ymd: str,
    page_size: int = 40,
    page_no: int = 1,
) -> dict[str, Any]:
    return {
        "dma_pageInfo": {
            "pageNo": page_no,
            "pageSize": page_size,
            "bfPageNo": "",
            "startRowNo": "",
            "totalCnt": "",
            "totalYn": "Y",
            "groupTotalCount": "",
        },
        "dma_srchGdsDtlSrchInfo": {
            "rletDspslSpcCondCd": "",
            "bidDvsCd": "000331",
            "mvprpRletDvsCd": "00031R",
            "cortAuctnSrchCondCd": "0004601",
            "rprsAdongSdCd": "", "rprsAdongSggCd": "", "rprsAdongEmdCd": "",
            "rdnmSdCd": "", "rdnmSggCd": "", "rdnmNo": "",
            "mvprpDspslPlcAdongSdCd": "", "mvprpDspslPlcAdongSggCd": "", "mvprpDspslPlcAdongEmdCd": "",
            "rdDspslPlcAdongSdCd": "", "rdDspslPlcAdongSggCd": "", "rdDspslPlcAdongEmdCd": "",
            "cortOfcCd": court_code, "jdbnCd": "", "execrOfcDvsCd": "",
            "lclDspslGdsLstUsgCd": "", "mclDspslGdsLstUsgCd": "", "sclDspslGdsLstUsgCd": "",
            "cortAuctnMbrsId": "", "aeeEvlAmtMin": "", "aeeEvlAmtMax": "",
            "lwsDspslPrcRateMin": "", "lwsDspslPrcRateMax": "",
            "flbdNcntMin": "", "flbdNcntMax": "", "objctArDtsMin": "", "objctArDtsMax": "",
            "mvprpArtclKndCd": "", "mvprpArtclNm": "", "mvprpAtchmPlcTypCd": "",
            "notifyLoc": "off", "lafjOrderBy": "", "pgmId": "PGJ151F01", "csNo": "",
            "cortStDvs": "1", "statNum": 1,
            "bidBgngYmd": begin_ymd, "bidEndYmd": end_ymd,
            "dspslDxdyYmd": "", "fstDspslHm": "", "scndDspslHm": "", "thrdDspslHm": "", "fothDspslHm": "",
            "dspslPlcNm": "", "lwsDspslPrcMin": "", "lwsDspslPrcMax": "",
            "grbxTypCd": "", "gdsVendNm": "", "fuelKndCd": "",
            "carMdyrMax": "", "carMdyrMin": "", "carMdlNm": "", "sideDvsCd": "",
        },
    }


@dataclass
class CourtAuctionSource:
    """지정 법원 관할의 경매 물건 중 타겟 시군구만 매물 소스로 가져온다."""

    court_name: str = "서울남부지방법원"
    court_code: str | None = None
    target_districts: tuple[str, ...] = ("양천구", "강서구", "구로구", "영등포구")
    begin_ymd: str | None = None
    end_ymd: str | None = None
    page_size: int = MAX_PAGE_SIZE
    max_pages: int = MAX_PAGES
    fetcher: SearchFetcher | None = None
    _targets: frozenset[str] = field(init=False, default=frozenset())

    def __post_init__(self) -> None:
        self._targets = frozenset(self.target_districts)

    def fetch(self) -> list[Listing]:
        code = self.court_code or COURT_CODES.get(self.court_name)
        if not code:
            print(f"[court] 알 수 없는 법원: {self.court_name}")
            return []
        begin, end = self._date_range()
        get = self.fetcher or _live_search
        page_size = min(self.page_size, MAX_PAGE_SIZE)
        listings: list[Listing] = []
        seen: set[str] = set()
        for page_no in range(1, self.max_pages + 1):
            body = build_search_body(code, begin, end, page_size=page_size, page_no=page_no)
            try:
                payload = json.loads(get(body))
            except Exception as error:  # noqa: BLE001 — 외부 사이트, 어떤 실패든 흡수
                print(f"[court] 법원경매 조회 실패 (page {page_no}): {error}")
                break
            data = payload.get("data") or {}
            items = data.get("dlt_srchResult") or []
            if not items:
                break
            for item in items:
                if not isinstance(item, dict) or item.get("hjguSigu") not in self._targets:
                    continue
                listing = _listing_from_item(item)
                if listing is None or listing.external_id in seen:
                    continue
                seen.add(listing.external_id)
                listings.append(listing)
            total = _to_int(data.get("dma_pageInfo", {}).get("totalCnt"))
            if page_no * page_size >= total:
                break
        return listings

    def _date_range(self) -> tuple[str, str]:
        if self.begin_ymd and self.end_ymd:
            return self.begin_ymd, self.end_ymd
        today = datetime.now(timezone.utc)
        return today.strftime("%Y%m%d"), (today + timedelta(days=SEARCH_WINDOW_DAYS)).strftime("%Y%m%d")


def _to_int(value: Any) -> int:
    try:
        return int(str(value).replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0


def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _listing_from_item(item: dict[str, Any]) -> Listing | None:
    case_no = str(item.get("srnSaNo", "")).strip()
    item_ser = str(item.get("maemulSer", "")).strip() or "1"
    if not case_no:
        return None
    location = " ".join(
        part
        for part in (
            str(item.get("hjguSido", "")).strip(),
            str(item.get("hjguSigu", "")).strip(),
            str(item.get("hjguDong", "")).strip(),
            str(item.get("daepyoLotno", "")).strip(),
        )
        if part
    )
    usage = str(item.get("dspslUsgNm", "")).strip()
    lowest = _to_int(item.get("minmaePrice"))
    appraisal = _to_int(item.get("gamevalAmt"))
    yuchal = _to_int(item.get("yuchalCnt"))
    note_parts = [f"법원경매 {case_no}"]
    if appraisal:
        note_parts.append(f"감정가 {appraisal:,}원")
    if lowest:
        note_parts.append(f"최저매각가 {lowest:,}원")
    if appraisal and lowest and appraisal > 0:
        note_parts.append(f"최저/감정 {round(lowest / appraisal * 100)}%")
    if yuchal:
        note_parts.append(f"유찰 {yuchal}회")
    sale_date = str(item.get("maeGiil", "")).strip()
    if sale_date and len(sale_date) == 8:
        note_parts.append(f"매각기일 {sale_date[:4]}.{sale_date[4:6]}.{sale_date[6:]}")
    court = str(item.get("jiwonNm", "")).strip()
    dept = str(item.get("jpDeptNm", "")).strip()
    if court:
        note_parts.append(f"{court} {dept}".strip())
    note_parts.append("법원경매정보(courtauction.go.kr)에서 사건번호로 검색")

    building_desc = str(item.get("pjbBuldList", "")).strip()
    is_land = usage in ("대지", "전", "답", "임야", "토지", "잡종지", "도로")
    return Listing(
        source="court",
        external_id=f"{case_no}-{item_ser}",
        title=f"[경매] {location}" + (f" ({usage})" if usage else ""),
        location=location or case_no,
        deposit=lowest,
        monthly_rent=0,
        area_m2=0.0,
        floor=None,
        premium=None,
        url=BASE_URL,
        property_type="land" if is_land else "building",
        usage=usage or None,
        appraisal_price=appraisal or None,
        min_bid_price=lowest or None,
        fail_count=yuchal or None,
        sale_date=sale_date if len(sale_date) == 8 else None,
        buildable_note=" · ".join(note_parts) + (f" · {building_desc}" if building_desc else ""),
        cs_no=case_no,
        cort_ofc_cd=str(item.get("boCd", "")).strip() or None,
        gds_seq=item_ser,
        latitude=_to_float(item.get("wgs84Ycordi")),
        longitude=_to_float(item.get("wgs84Xcordi")),
        building_area_m2=_to_float(item.get("maxArea")),
    )


def _live_search(body: dict[str, Any]) -> str:
    """실제 법원경매 사이트 호출 — 세션 쿠키 확보 후 검색."""
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    index_req = urllib.request.Request(
        INDEX_URL,
        headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Upgrade-Insecure-Requests": "1",
        },
    )
    opener.open(index_req, timeout=REQUEST_TIMEOUT_SECONDS).read(1024)
    search_req = urllib.request.Request(
        SEARCH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "User-Agent": _UA,
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": SEARCH_REFERER,
            "submissionid": "mf_wfm_mainFrame_sbm_selectGdsDtlSrch",
            "sc-userid": "SYSTEM",
        },
    )
    with opener.open(search_req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")
