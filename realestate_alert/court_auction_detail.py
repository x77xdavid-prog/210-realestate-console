from __future__ import annotations
import json, urllib.request
from http.cookiejar import CookieJar
from typing import Any, Callable
from realestate_alert.models import AuctionDetail, Photo, StatusItem, BidEvent

BASE_URL = "https://www.courtauction.go.kr"
INDEX_URL = f"{BASE_URL}/pgj/index.on"
DETAIL_URL = f"{BASE_URL}/pgj/pgj15B/selectAuctnCsSrchRslt.on"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
TIMEOUT = 20

DetailFetcher = Callable[[dict[str, Any]], str]

STATUS_LABELS = {
    "00083001": "위치 및 주위환경", "00083003": "교통상황", "00083005": "인접 도로상태",
    "00083006": "이용상태", "00083009": "토지의 형상 및 이용상태", "00083011": "토지이용계획 및 제한상태",
    "00083014": "공부와의 차이", "00083015": "건물의 구조", "00083017": "설비내역",
    "00083026": "기타참고사항(임대관계 등)",
}
STATUS_ORDER = ["00083001", "00083003", "00083015", "00083006", "00083017",
                "00083009", "00083005", "00083011", "00083014", "00083026"]
_TAG_KEYWORDS = {
    "임차권등기": "임차권등기", "가등기": "선순위가등기", "선순위": "선순위임차인",
    "유치권": "유치권", "법정지상권": "법정지상권", "지분": "지분매각", "위반건축물": "위반건축물",
    "대항력": "대항력", "별도등기": "별도등기",
}


def status_label(code: str) -> str:
    return STATUS_LABELS.get(code, code)


def bid_result(rslt: str | None, kind: str | None) -> str:
    if rslt == "002":
        return "유찰"
    if kind == "02":
        return "매각결정"
    if rslt in (None, "", "001"):
        return "진행"
    return "변경"


def extract_incumbrance_tags(text: str) -> tuple[str, ...]:
    text = text or ""
    seen: list[str] = []
    for key, tag in _TAG_KEYWORDS.items():
        if key in text and tag not in seen:
            seen.append(tag)
    return tuple(seen)


def build_detail_body(cs_no: str, cort_ofc_cd: str, gds_seq: str) -> dict[str, Any]:
    return {"dma_srchGdsDtlSrch": {
        "csNo": cs_no, "cortOfcCd": cort_ofc_cd, "dspslGdsSeq": gds_seq, "pgmId": "PGJ151F01"}}


def _to_int(v: Any) -> int | None:
    try:
        return int(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _to_float(v: Any) -> float | None:
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_detail(payload: dict[str, Any], identity: str,
                 photo_paths: dict[int, str]) -> AuctionDetail:
    r = (payload.get("data") or {}).get("dma_result") or {}
    base = r.get("csBaseInfo") or {}
    dx = r.get("dspslGdsDxdyInfo") or {}
    obj = (r.get("gdsDspslObjctLst") or [{}])[0]

    status_items: list[StatusItem] = []
    for code in STATUS_ORDER:
        for a in r.get("aeeWevlMnpntLst") or []:
            if a.get("aeeWevlMnpntItmCd") == code:
                status_items.append(StatusItem(status_label(code), (a.get("aeeWevlMnpntCtt") or "").strip()))
                break

    bids: list[BidEvent] = []
    for g in r.get("gdsDspslDxdyLst") or []:
        bids.append(BidEvent(str(g.get("dxdyYmd", "")), _to_int(g.get("tsLwsDspslPrc")),
                             bid_result(g.get("auctnDxdyRsltCd"), g.get("auctnDxdyKndCd"))))

    photos = tuple(Photo(path, "", seq) for seq, path in sorted(photo_paths.items()))
    incum_text = (dx.get("ndstrcRghCtt") or "").strip()
    incumbrances = tuple(s.strip() for s in incum_text.splitlines() if s.strip()) or ((incum_text,) if incum_text else ())

    return AuctionDetail(
        identity=identity, court=str(base.get("cortOfcNm", "")).strip(),
        dept=str(dx.get("cortSptNm") or "").strip(),
        case_no=str(base.get("userCsNo") or base.get("csNo", "")).strip(),
        addr_road=str(obj.get("userPrintSt", "")).strip(),
        addr_jibun=str(obj.get("rprsLtnoAddr", "")).strip(),
        usage=str(dx.get("realMulKind", "")).strip(),
        auction_type="강제경매" if "강제" in str(base.get("csNm", "")) else "경매",
        land_m2=None, bldg_m2=_to_float(obj.get("objctArDts")),
        appraisal=_to_int(dx.get("aeeEvlAmt")), min_bid=_to_int(dx.get("fstPbancLwsDspslPrc")),
        deposit=None, claim_amt=_to_int(base.get("clmAmt")),
        fail_count=_to_int(dx.get("flbdNcnt")), sale_date=str(dx.get("dspslDxdyYmd", "")).strip() or None,
        photos=photos, status_items=tuple(status_items), bid_history=tuple(bids),
        incumbrances=incumbrances, doc_ecid=str(dx.get("dspslGdsSpcfcEcdocId", "")).strip() or None,
        latitude=_to_float(obj.get("stYcrd")), longitude=_to_float(obj.get("stXcrd")),
    )


def fetch_detail(cs_no: str, cort_ofc_cd: str, gds_seq: str,
                 fetcher: DetailFetcher | None = None) -> dict[str, Any]:
    body = build_detail_body(cs_no, cort_ofc_cd, gds_seq)
    raw = (fetcher or _live_detail)(body)
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        return {}


def _live_detail(body: dict[str, Any]) -> str:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    idx = urllib.request.Request(INDEX_URL, headers={"User-Agent": _UA})
    opener.open(idx, timeout=TIMEOUT).read(1024)
    req = urllib.request.Request(DETAIL_URL, data=json.dumps(body).encode("utf-8"),
        headers={"User-Agent": _UA, "Accept": "application/json",
                 "Content-Type": "application/json;charset=UTF-8",
                 "Referer": f"{INDEX_URL}?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml", "sc-userid": "SYSTEM"})
    with opener.open(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")
