# 경매 상세·풍부한 게시판·월별 캘린더 (§1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대법원 법원경매정보(courtauction)에서 경매 물건의 사진·현황·기일·권리(인수사항)를 직접 수집해, 저번에 비었던 게시판 카드/상세를 풍부하게 채우고 월별 경매 캘린더를 추가한다.

**Architecture:** 기존 `realestate_alert` 패키지에 **제자리 확장**. 목록은 가벼운 `Listing`, 상세는 무거운 `AuctionDetail`로 분리. 신규 수집기 2종(상세·기일별)과 사진 모듈을 추가하고, stdlib `http.server` 웹서버에 엔드포인트 3종을 더한다. 승인된 v2 샘플 UI를 `web/`에 이식. 모든 외부 호출은 fetcher 주입으로 테스트.

**Tech Stack:** Python 3.11+ 표준 라이브러리(`urllib`, `sqlite3`, `http.server`, `unittest`), Pillow(사진 압축, 신규 의존성), 바닐라 JS/CSS 프런트.

## Global Constraints

- 외부 호출 실패는 **빈 결과/None 흡수** — 배치/요청 중단 금지(기존 패턴).
- 외부 호출은 `Callable[[dict], str]` **fetcher 주입**으로 단위테스트(네트워크 없음). 기존 `court_auction.SearchFetcher` 동일.
- 테스트 프레임워크 **unittest**, 실행 `python -m unittest`. 한 태스크 = RED→GREEN→commit.
- `Listing`은 `@dataclass(frozen=True)` 유지. 신규 구조도 frozen.
- 상세 조회는 **신규/관심 물건 한정** · 호출 간격 · 캐시(전건 조회 금지).
- 사진은 **압축(JPEG 품질 70·최대 변 1280px)** 후 로컬 저장, **병원적합 후보만**. 원문 문서(명세서·감정서)는 저장 금지·courtauction 링크.
- 커밋 메시지: `<type>: <설명>` (feat/fix/test/docs), attribution 줄 없음.
- 작업 브랜치: `feat/court-detail-board-calendar` (이미 생성됨).

---

## File Structure

| 파일 | 책임 | 신규/수정 |
|---|---|---|
| `realestate_alert/models.py` | `AuctionDetail`·`Photo`·`StatusItem`·`BidEvent` + `Listing` 카드필드 | 수정 |
| `realestate_alert/court_auction.py` | 목록 → 상세 조회 키(csNo·cortOfcCd·dspslGdsSeq)·좌표·면적 보강 | 수정 |
| `realestate_alert/court_auction_detail.py` | 상세 fetch + 응답 파서(사진메타·현황·기일·권리·가격) | 신규 |
| `realestate_alert/court_calendar.py` | 법원별 기일 날짜 + 날짜별 건수 집계 | 신규 |
| `realestate_alert/photos.py` | base64 → 압축·저장·경로·정렬 | 신규 |
| `realestate_alert/store.py` | `auction_detail`·`calendar_cache` 테이블 + upsert/get | 수정 |
| `realestate_alert/web_server.py` | `/api/listing/detail`·`/api/photo`·`/api/calendar` + `_listings_payload` 확장 | 수정 |
| `realestate_alert/service.py` | 스캔 시 후보 상세 보강 연결 | 수정 |
| `web/app.js`, `web/styles.css`, `web/index.html` | 풍부한 카드·상세·캘린더 (v2 샘플 이식) | 수정 |
| `tests/test_court_auction_detail.py` 등 | 단위/통합 테스트 | 신규/수정 |
| `samples/court-detail-2024ta58264.sample.json` | 파서 픽스처 | 이관 |

---

## Task 1: 모델 — AuctionDetail + 값객체 + Listing 카드필드

**Files:**
- Modify: `realestate_alert/models.py`
- Test: `tests/test_models_detail.py` (신규)

**Interfaces:**
- Produces: `Photo(file, dvs, seq)`, `StatusItem(label, text)`, `BidEvent(date, low, result)`, `AuctionDetail(...)`; `Listing`에 `thumbnail_path: str|None=None`, `photo_count: int|None=None`, `incumbrance_tags: tuple[str,...]=()`, `cs_no: str|None=None`, `cort_ofc_cd: str|None=None`, `gds_seq: str|None=None`, `latitude/longitude: float|None=None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models_detail.py
import unittest
from realestate_alert.models import AuctionDetail, Photo, StatusItem, BidEvent, Listing


class ModelDetailTests(unittest.TestCase):
    def test_auction_detail_holds_rich_fields(self):
        d = AuctionDetail(
            identity="court:2024타경58264-1", court="서울서부지방법원", dept="경매7계",
            case_no="2024타경58264", addr_road="서울 마포구 만리재옛2길 14",
            addr_jibun="서울 마포구 신공덕동 5-38", usage="다세대", auction_type="강제경매",
            land_m2=44.01, bldg_m2=51.14, appraisal=594000000, min_bid=32656000,
            deposit=3265600, claim_amt=563644488, fail_count=13, sale_date="20260623",
            photos=(Photo("court:x/01.jpg", "외관", 1),),
            status_items=(StatusItem("위치 및 주위환경", "공덕역 인근"),),
            bid_history=(BidEvent("20260519", 40820000, "유찰"),),
            incumbrances=("임차권등기 보증금 5.3억 인수",),
            doc_ecid="ECID123", latitude=37.5, longitude=126.9,
        )
        self.assertEqual(d.fail_count, 13)
        self.assertEqual(d.photos[0].seq, 1)
        self.assertEqual(d.bid_history[0].result, "유찰")

    def test_listing_card_fields_default_empty(self):
        l = Listing(source="court", external_id="x", title="t", location="l",
                    deposit=0, monthly_rent=0, area_m2=0.0, floor=None, premium=None, url="u")
        self.assertIsNone(l.thumbnail_path)
        self.assertEqual(l.incumbrance_tags, ())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_models_detail -v`
Expected: FAIL — `ImportError: cannot import name 'AuctionDetail'`

- [ ] **Step 3: Write minimal implementation**

`models.py`에 추가(파일 상단 import는 그대로):

```python
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
```

`Listing` 데이터클래스 끝(`buildable_note` 다음 줄)에 카드 필드 추가:

```python
    thumbnail_path: str | None = None
    photo_count: int | None = None
    incumbrance_tags: tuple[str, ...] = ()
    cs_no: str | None = None
    cort_ofc_cd: str | None = None
    gds_seq: str | None = None
    latitude: float | None = None
    longitude: float | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_models_detail -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full suite (회귀 확인)**

Run: `python -m unittest`
Expected: 기존 테스트 전부 PASS (frozen 필드 추가는 기본값이라 호환)

- [ ] **Step 6: Commit**

```bash
git add realestate_alert/models.py tests/test_models_detail.py
git commit -m "feat: AuctionDetail 모델 + Listing 카드 필드"
```

---

## Task 2: 목록 수집기 — 상세 조회 키·좌표·면적 보강

**Files:**
- Modify: `realestate_alert/court_auction.py` (`_listing_from_item`, 약 153–210줄)
- Test: `tests/test_court_auction.py` (기존에 케이스 추가)

**Interfaces:**
- Consumes: Task 1의 `Listing` 새 필드.
- Produces: `Listing`에 `cs_no`(=srnSaNo), `cort_ofc_cd`(=boCd), `gds_seq`(=maemulSer), `latitude/longitude`(wgs84Ycordi/Xcordi), `building_area_m2`(maxArea) 채워짐 → Task 7 상세 조회에 사용.

- [ ] **Step 1: Write the failing test** — `tests/test_court_auction.py`의 `SAMPLE_ITEMS[0]`에 `"boCd":"B000212","wgs84Xcordi":"126.85","wgs84Ycordi":"37.52","maxArea":"900"` 추가하고 케이스 추가:

```python
    def test_fetch_captures_detail_keys(self):
        source = CourtAuctionSource(
            court_code="B000212", begin_ymd="20260612", end_ymd="20260710",
            fetcher=lambda body: _result(SAMPLE_ITEMS),
        )
        listing = source.fetch()[0]
        self.assertEqual(listing.cs_no, "2024타경1009")
        self.assertEqual(listing.cort_ofc_cd, "B000212")
        self.assertEqual(listing.gds_seq, "1")
        self.assertAlmostEqual(listing.latitude, 37.52, places=2)
```

- [ ] **Step 2: Run → FAIL** (`AttributeError`/`None`)

Run: `python -m unittest tests.test_court_auction -v`

- [ ] **Step 3: Implement** — `_listing_from_item`의 `return Listing(...)`에 인자 추가:

```python
    cs_no=case_no,
    cort_ofc_cd=str(item.get("boCd", "")).strip() or None,
    gds_seq=item_ser,
    latitude=_to_float(item.get("wgs84Ycordi")),
    longitude=_to_float(item.get("wgs84Xcordi")),
    building_area_m2=_to_float(item.get("maxArea")),
```

그리고 파일에 헬퍼 추가(없으면):

```python
def _to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Run → PASS** (`python -m unittest tests.test_court_auction -v`)
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/court_auction.py tests/test_court_auction.py
git commit -m "feat: 목록 수집기에 상세 조회 키·좌표·면적 보강"
```

---

## Task 3: 상세 수집기 — fetch + 응답 파서

**Files:**
- Create: `realestate_alert/court_auction_detail.py`
- Test: `tests/test_court_auction_detail.py`
- Fixture: `samples/court-detail-2024ta58264.sample.json` (v2에서 이관)

**Interfaces:**
- Consumes: Task 1 모델, Listing의 `cs_no/cort_ofc_cd/gds_seq`.
- Produces: `parse_detail(payload: dict, identity: str, photo_paths: dict[int,str]) -> AuctionDetail` 와 `fetch_detail(cs_no, cort_ofc_cd, gds_seq, fetcher: DetailFetcher|None=None) -> dict` (원시 payload). `DetailFetcher = Callable[[dict], str]`. 현황코드 매핑·기일 결과코드 매핑·인수사항→권리태그(`incumbrance_tags`)는 이 모듈에서.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_court_auction_detail.py
import unittest
from realestate_alert.court_auction_detail import (
    parse_detail, status_label, bid_result, extract_incumbrance_tags,
)

PAYLOAD = {"data": {"dma_result": {
    "csBaseInfo": {"cortOfcNm": "서울서부지방법원", "csNo": "2024타경58264",
                   "userCsNo": "2024타경58264", "clmAmt": "563644488"},
    "dspslGdsDxdyInfo": {"aeeEvlAmt": "594000000", "fstPbancLwsDspslPrc": "32656000",
        "flbdNcnt": "13", "dspslDxdyYmd": "20260623", "cortSptNm": "경매7계",
        "ndstrcRghCtt": "을구 5번 임차권등기(보증금 530,000,000원) 매수인 인수. 갑구 7번 가등기 인수.",
        "realMulKind": "다세대"},
    "gdsDspslObjctLst": [{"userPrintSt": "서울 마포구 만리재옛2길 14", "rprsLtnoAddr": "서울 마포구 신공덕동 5-38",
        "bldDtlDts": "5층501호", "stXcrd": "126.9", "stYcrd": "37.5"}],
    "csPicLst": [{"cortAuctnPicSeq": "1", "cortAuctnPicDvsCd": "000241", "picTitlNm": "a.jpg"}],
    "gdsDspslDxdyLst": [
        {"dxdyYmd": "20260519", "tsLwsDspslPrc": 40820000, "auctnDxdyRsltCd": "002", "auctnDxdyKndCd": "01"},
        {"dxdyYmd": "20260623", "tsLwsDspslPrc": 32656000, "auctnDxdyRsltCd": None, "auctnDxdyKndCd": "01"},
        {"dxdyYmd": "20260630", "tsLwsDspslPrc": 0, "auctnDxdyRsltCd": None, "auctnDxdyKndCd": "02"}],
    "aeeWevlMnpntLst": [{"aeeWevlMnpntItmCd": "00083001", "aeeWevlMnpntCtt": "공덕역 인근"}],
}}}


class DetailParseTests(unittest.TestCase):
    def test_status_label_maps_code(self):
        self.assertEqual(status_label("00083011"), "토지이용계획 및 제한상태")

    def test_bid_result_maps(self):
        self.assertEqual(bid_result("002", "01"), "유찰")
        self.assertEqual(bid_result(None, "01"), "진행")
        self.assertEqual(bid_result(None, "02"), "매각결정")

    def test_incumbrance_tags_extracted(self):
        tags = extract_incumbrance_tags("을구 임차권등기 ... 갑구 가등기 인수 ... 선순위")
        self.assertIn("임차권등기", tags)
        self.assertIn("선순위가등기", tags)

    def test_parse_detail_builds_auction_detail(self):
        d = parse_detail(PAYLOAD, "court:2024타경58264-1", {1: "court:x/01.jpg"})
        self.assertEqual(d.appraisal, 594000000)
        self.assertEqual(d.fail_count, 13)
        self.assertEqual(d.usage, "다세대")
        self.assertEqual(len(d.bid_history), 3)
        self.assertEqual(d.bid_history[1].result, "진행")
        self.assertEqual(d.status_items[0].label, "위치 및 주위환경")
        self.assertEqual(d.photos[0].file, "court:x/01.jpg")
        self.assertIn("임차권등기", d.incumbrances[0])
```

- [ ] **Step 2: Run → FAIL** (`ModuleNotFoundError`)

Run: `python -m unittest tests.test_court_auction_detail -v`

- [ ] **Step 3: Implement** `realestate_alert/court_auction_detail.py`

```python
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
```

- [ ] **Step 4: Run → PASS** (`python -m unittest tests.test_court_auction_detail -v`)
- [ ] **Step 5: Fixture 이관**

```bash
cp "../부동산매물 자동 검색v2/samples/court-detail-2024ta58264.sample.json" samples/
git add samples/court-detail-2024ta58264.sample.json
```

- [ ] **Step 6: Commit**

```bash
git add realestate_alert/court_auction_detail.py tests/test_court_auction_detail.py samples/
git commit -m "feat: courtauction 상세 수집기 + 응답 파서"
```

---

## Task 4: 사진 모듈 — base64 → 압축·저장·정렬

**Files:**
- Create: `realestate_alert/photos.py`
- Test: `tests/test_photos.py`

**Interfaces:**
- Produces: `save_photos(cs_pic_list: list[dict], identity: str, base_dir: Path) -> dict[int, str]` — seq→상대경로(`{identity-safe}/NN.jpg`). 구분코드 우선순위로 건물사진 먼저. base64 디코딩→Pillow 압축. Pillow 없거나 디코딩 실패 시 해당 장만 생략.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_photos.py
import base64, io, unittest
from pathlib import Path
import tempfile
from realestate_alert.photos import save_photos, PIC_ORDER

def _tiny_jpeg_b64():
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()

class PhotoTests(unittest.TestCase):
    def test_saves_and_orders(self):
        b64 = _tiny_jpeg_b64()
        pics = [
            {"cortAuctnPicSeq": "1", "cortAuctnPicDvsCd": "000244", "picFile": b64},  # 지적도 → 뒤
            {"cortAuctnPicSeq": "2", "cortAuctnPicDvsCd": "000241", "picFile": b64},  # 외관 → 앞
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_photos(pics, "court:2024타경58264-1", Path(tmp))
            self.assertEqual(len(paths), 2)
            first = paths[min(paths)]
            self.assertTrue(first.endswith("/01.jpg"))
            self.assertTrue((Path(tmp) / first).exists())

    def test_bad_base64_skipped(self):
        pics = [{"cortAuctnPicSeq": "1", "cortAuctnPicDvsCd": "000241", "picFile": "!!notb64!!"}]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(save_photos(pics, "x", Path(tmp)), {})
```

- [ ] **Step 2: Run → FAIL** — Pillow 미설치면 먼저 설치:

```bash
pip install Pillow
echo "Pillow" >> requirements.txt
```
Run: `python -m unittest tests.test_photos -v` → FAIL (`ModuleNotFoundError: photos`)

- [ ] **Step 3: Implement** `realestate_alert/photos.py`

```python
from __future__ import annotations
import base64, io, re
from pathlib import Path

PIC_ORDER = {"000241": 0, "000245": 1, "000247": 2, "000244": 3}  # 외관·내부 먼저, 지적도 뒤
MAX_SIDE = 1280
QUALITY = 70


def _safe(identity: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣_-]", "_", identity)


def save_photos(cs_pic_list: list[dict], identity: str, base_dir: Path) -> dict[int, str]:
    try:
        from PIL import Image
    except ImportError:
        return {}
    folder = _safe(identity)
    out_dir = base_dir / folder
    ordered = sorted(cs_pic_list, key=lambda p: (PIC_ORDER.get(p.get("cortAuctnPicDvsCd"), 9),
                                                 int(p.get("cortAuctnPicSeq", 0) or 0)))
    result: dict[int, str] = {}
    n = 0
    for p in ordered:
        b64 = p.get("picFile")
        if not b64:
            continue
        try:
            raw = base64.b64decode(b64, validate=True)
            img = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:  # noqa: BLE001
            continue
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        n += 1
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{n:02d}.jpg"
        img.save(out_dir / fname, "JPEG", quality=QUALITY, optimize=True)
        result[n] = f"{folder}/{fname}"
    return result
```

- [ ] **Step 4: Run → PASS** (`python -m unittest tests.test_photos -v`)
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/photos.py tests/test_photos.py requirements.txt
git commit -m "feat: 사진 base64 압축·저장 모듈"
```

---

## Task 5: 저장소 — auction_detail 영속화

**Files:**
- Modify: `realestate_alert/store.py` (`initialize()` + 메서드)
- Test: `tests/test_store.py` (케이스 추가)

**Interfaces:**
- Produces: `ListingStore.upsert_detail(identity: str, detail_json: dict) -> None`, `ListingStore.get_detail(identity: str) -> dict | None`. 테이블 `auction_detail(identity PK, detail_json, updated_at)`.

- [ ] **Step 1: Write the failing test** (`tests/test_store.py`에 추가)

```python
    def test_upsert_and_get_detail(self):
        import tempfile
        from pathlib import Path
        from realestate_alert.store import ListingStore
        with tempfile.TemporaryDirectory() as tmp:
            store = ListingStore(Path(tmp) / "t.db")
            store.initialize()
            store.upsert_detail("court:x-1", {"appraisal": 1, "photos": ["a"]})
            store.upsert_detail("court:x-1", {"appraisal": 2, "photos": ["a", "b"]})  # 덮어쓰기
            got = store.get_detail("court:x-1")
            self.assertEqual(got["appraisal"], 2)
            self.assertIsNone(store.get_detail("court:none"))
```

- [ ] **Step 2: Run → FAIL** (`AttributeError: upsert_detail`)

Run: `python -m unittest tests.test_store -v`

- [ ] **Step 3: Implement** — `initialize()`의 마지막 `connection.execute(...)` 다음에 테이블 추가:

```python
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS auction_detail (
                        identity TEXT PRIMARY KEY,
                        detail_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
```

클래스에 메서드 추가:

```python
    def upsert_detail(self, identity: str, detail_json: dict) -> None:
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO auction_detail (identity, detail_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(identity) DO UPDATE SET
                        detail_json = excluded.detail_json, updated_at = CURRENT_TIMESTAMP
                    """,
                    (identity, json.dumps(detail_json, ensure_ascii=False)),
                )

    def get_detail(self, identity: str) -> dict | None:
        self.initialize()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT detail_json FROM auction_detail WHERE identity = ?", (identity,)
            ).fetchone()
        return json.loads(row[0]) if row else None
```

- [ ] **Step 4: Run → PASS** (`python -m unittest tests.test_store -v`)
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/store.py tests/test_store.py
git commit -m "feat: auction_detail 저장/조회"
```

---

## Task 6: 캘린더 수집기 — 법원별 기일·날짜별 건수

**Files:**
- Create: `realestate_alert/court_calendar.py`
- Test: `tests/test_court_calendar.py`

**Interfaces:**
- Produces: `dates_of(cort_ofc_cd, fetcher=None) -> list[str]` (기일 날짜), `month_counts(courts: list[str], count_fetcher) -> dict[str, dict[str, int]]` (date→{court→count}). `DatesFetcher=Callable[[dict],str]`, `CountFetcher=Callable[[str,str],int]`(cort,ymd→cnt) 주입.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_court_calendar.py
import json, unittest
from realestate_alert.court_calendar import dates_of, month_counts

def _dxdy(dates):
    return json.dumps({"data": {"dlt_rletDxdySrchLst": [{"dspslDxdyYmd": d} for d in dates]}})

class CalendarTests(unittest.TestCase):
    def test_dates_of_dedupes_sorted(self):
        out = dates_of("B000210", fetcher=lambda b: _dxdy(["20260625", "20260623", "20260623"]))
        self.assertEqual(out, ["20260623", "20260625"])

    def test_dates_of_absorbs_error(self):
        def boom(b): raise RuntimeError("x")
        self.assertEqual(dates_of("B000210", fetcher=boom), [])

    def test_month_counts_aggregates(self):
        dmap = {"서울중앙": ["20260623"], "서울서부": ["20260623", "20260630"]}
        counts = month_counts(
            courts=list(dmap),
            dates_fetcher=lambda c: dmap[c],
            count_fetcher=lambda c, ymd: 10,
        )
        self.assertEqual(counts["20260623"]["서울중앙"], 10)
        self.assertEqual(counts["20260623"]["__total__"], 20)
        self.assertEqual(counts["20260630"]["__total__"], 10)
```

- [ ] **Step 2: Run → FAIL** (`ModuleNotFoundError`)

Run: `python -m unittest tests.test_court_calendar -v`

- [ ] **Step 3: Implement** `realestate_alert/court_calendar.py`

```python
from __future__ import annotations
import json, urllib.request
from http.cookiejar import CookieJar
from typing import Any, Callable

BASE_URL = "https://www.courtauction.go.kr"
INDEX_URL = f"{BASE_URL}/pgj/index.on"
DXDY_URL = f"{BASE_URL}/pgj/pgj153/selectDxdyRletSrchRslt.on"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")

DatesFetcher = Callable[[dict[str, Any]], str]


def dates_of(cort_ofc_cd: str, fetcher: DatesFetcher | None = None) -> list[str]:
    body = {"dma_srchRletDxdy": {"cortOfcCd": cort_ofc_cd, "bidDvsCd": "000331"}}
    try:
        raw = (fetcher or _live_dates)(body)
        data = (json.loads(raw).get("data") or {})
        lst = data.get("dlt_rletDxdySrchLst") or []
        return sorted({str(x.get("dspslDxdyYmd")) for x in lst if x.get("dspslDxdyYmd")})
    except Exception:  # noqa: BLE001
        return []


def month_counts(courts: list[str], dates_fetcher: Callable[[str], list[str]],
                 count_fetcher: Callable[[str, str], int]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for court in courts:
        for ymd in dates_fetcher(court):
            try:
                c = count_fetcher(court, ymd)
            except Exception:  # noqa: BLE001
                c = 0
            slot = out.setdefault(ymd, {"__total__": 0})
            slot[court] = c
            slot["__total__"] += c
    return out


def _live_dates(body: dict[str, Any]) -> str:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(urllib.request.Request(INDEX_URL, headers={"User-Agent": _UA}), timeout=20).read(1024)
    req = urllib.request.Request(DXDY_URL, data=json.dumps(body).encode("utf-8"),
        headers={"User-Agent": _UA, "Content-Type": "application/json;charset=UTF-8", "sc-userid": "SYSTEM"})
    with opener.open(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")
```

- [ ] **Step 4: Run → PASS** (`python -m unittest tests.test_court_calendar -v`)
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/court_calendar.py tests/test_court_calendar.py
git commit -m "feat: 기일별 캘린더 집계 수집기"
```

---

## Task 7: 웹 — /api/listing/detail 엔드포인트

**Files:**
- Modify: `realestate_alert/web_server.py` (do_GET 라우팅 + 헬퍼)
- Test: `tests/test_web_server.py` (헬퍼 단위 테스트)

**Interfaces:**
- Consumes: Task 3 `fetch_detail`/`parse_detail`, Task 4 `save_photos`, Task 5 `get_detail/upsert_detail`.
- Produces: `_detail_payload(config_path, identity, cs_no, cort_ofc_cd, gds_seq) -> dict`. 캐시 우선(get_detail) → 없으면 fetch→사진저장→parse→직렬화 후 upsert. do_GET에 `/api/listing/detail` 분기.

- [ ] **Step 1: Write the failing test** — fetcher/saver 주입형 헬퍼를 테스트:

```python
    def test_detail_payload_uses_cache(self):
        import tempfile
        from pathlib import Path
        from realestate_alert.web_server import build_detail_payload
        from realestate_alert.store import ListingStore
        with tempfile.TemporaryDirectory() as tmp:
            store = ListingStore(Path(tmp) / "t.db"); store.initialize()
            store.upsert_detail("court:x-1", {"case_no": "2024타경1", "photos": []})
            payload = build_detail_payload(store, "court:x-1", "2024타경1", "B000210", "1",
                                           photo_dir=Path(tmp), fetcher=lambda b: (_ for _ in ()).throw(AssertionError("should not fetch")))
            self.assertEqual(payload["case_no"], "2024타경1")
```

- [ ] **Step 2: Run → FAIL** (`ImportError: build_detail_payload`)

Run: `python -m unittest tests.test_web_server -v`

- [ ] **Step 3: Implement** — `web_server.py`에 함수 추가:

```python
def build_detail_payload(store, identity, cs_no, cort_ofc_cd, gds_seq, photo_dir, fetcher=None):
    from realestate_alert.court_auction_detail import fetch_detail, parse_detail
    from realestate_alert.photos import save_photos
    from dataclasses import asdict
    cached = store.get_detail(identity)
    if cached:
        return cached
    payload = fetch_detail(cs_no, cort_ofc_cd, gds_seq, fetcher=fetcher)
    pics = (((payload.get("data") or {}).get("dma_result") or {}).get("csPicLst")) or []
    photo_paths = save_photos(pics, identity, photo_dir)
    detail = parse_detail(payload, identity, photo_paths)
    data = asdict(detail)
    store.upsert_detail(identity, data)
    return data
```

do_GET에 분기 추가(`/api/listings` 다음):

```python
            if self.path.startswith("/api/listing/detail"):
                q = parse_qs(urlparse(self.path).query)
                identity = (q.get("id") or [""])[0]
                cs_no = (q.get("cs") or [""])[0]
                cort = (q.get("court") or [""])[0]
                seq = (q.get("seq") or ["1"])[0]
                if not identity:
                    self._send_json({"error": "id 필요"}, status=400); return
                payload = build_detail_payload(_store(config_path), identity, cs_no, cort, seq,
                                               photo_dir=_photo_dir(config_path))
                self._send_json(payload); return
```

`_photo_dir(config_path)` 헬퍼 추가(데이터 디렉토리 하위 `photos/`):

```python
def _photo_dir(config_path: Path) -> Path:
    d = config_path.parent / "data" / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d
```

- [ ] **Step 4: Run → PASS** (`python -m unittest tests.test_web_server -v`)
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/web_server.py tests/test_web_server.py
git commit -m "feat: /api/listing/detail 엔드포인트(캐시 우선)"
```

---

## Task 8: 웹 — /api/photo 로컬 사진 서빙

**Files:**
- Modify: `realestate_alert/web_server.py`
- Test: `tests/test_web_server.py`

**Interfaces:**
- Produces: do_GET `/api/photo?path=<folder/NN.jpg>` → `_photo_dir` 하위 파일을 image/jpeg로 전송. 경로 탈출(`..`) 차단.

- [ ] **Step 1: Write the failing test**

```python
    def test_photo_path_rejects_traversal(self):
        from realestate_alert.web_server import safe_photo_path
        from pathlib import Path
        base = Path("/data/photos")
        self.assertIsNone(safe_photo_path(base, "../secret.txt"))
        self.assertIsNone(safe_photo_path(base, "/etc/passwd"))
        ok = safe_photo_path(base, "court_x-1/01.jpg")
        self.assertTrue(str(ok).replace("\\\\", "/").endswith("court_x-1/01.jpg"))
```

- [ ] **Step 2: Run → FAIL** (`ImportError: safe_photo_path`)
- [ ] **Step 3: Implement**

```python
def safe_photo_path(base: Path, rel: str) -> Path | None:
    if not rel or rel.startswith("/") or ".." in rel.replace("\\\\", "/").split("/"):
        return None
    candidate = (base / rel).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate
```

do_GET 분기:

```python
            if self.path.startswith("/api/photo"):
                q = parse_qs(urlparse(self.path).query)
                target = safe_photo_path(_photo_dir(config_path), (q.get("path") or [""])[0])
                if not target or not target.exists():
                    self.send_response(404); self.end_headers(); return
                data = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers(); self.wfile.write(data); return
```

- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/web_server.py tests/test_web_server.py
git commit -m "feat: /api/photo 로컬 사진 서빙(경로 탈출 차단)"
```

---

## Task 9: 웹 — /api/calendar 엔드포인트(캐시)

**Files:**
- Modify: `realestate_alert/web_server.py`, `realestate_alert/store.py`(calendar_cache)
- Test: `tests/test_web_server.py`

**Interfaces:**
- Produces: `/api/calendar?ym=YYYYMM&scope=seoul` → `{ym, days:{D:count}, courts_for:{date:{court:cnt}}}`. 일 1회 캐시(`calendar_cache(ym PK, json, updated_at)`); 캐시 있으면 재호출 안 함.

- [ ] **Step 1: Write the failing test**

```python
    def test_calendar_payload_cached(self):
        import tempfile
        from pathlib import Path
        from realestate_alert.web_server import build_calendar_payload
        from realestate_alert.store import ListingStore
        with tempfile.TemporaryDirectory() as tmp:
            store = ListingStore(Path(tmp) / "t.db"); store.initialize()
            calls = {"n": 0}
            def compute():
                calls["n"] += 1
                return {"ym": "202606", "days": {"23": 30}, "courts_for": {}}
            a = build_calendar_payload(store, "202606", compute)
            b = build_calendar_payload(store, "202606", compute)  # 캐시 → compute 1회
            self.assertEqual(a["days"]["23"], 30)
            self.assertEqual(calls["n"], 1)
```

- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** — store에 `calendar_cache` 테이블(Task 5 패턴) + `get_calendar(ym)`/`save_calendar(ym, data)`; web_server에:

```python
def build_calendar_payload(store, ym, compute):
    cached = store.get_calendar(ym)
    if cached:
        return cached
    data = compute()
    store.save_calendar(ym, data)
    return data
```

do_GET 분기(`/api/calendar`)에서 `compute`는 `court_calendar.month_counts`(서울 5법원, count_fetcher=목록 totalCnt)로 구성. 실패 시 빈 days.

- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/web_server.py realestate_alert/store.py tests/test_web_server.py
git commit -m "feat: /api/calendar 월별 집계(일1회 캐시)"
```

---

## Task 10: 웹 — _listings_payload 카드 필드 확장

**Files:**
- Modify: `realestate_alert/web_server.py` (`_listings_payload`, 약 864줄)
- Test: `tests/test_web_server.py`

**Interfaces:**
- Produces: 각 listing dict에 `thumbnail_url`(`/api/photo?path=`), `photo_count`, `incumbrance_tags`, `detail_link`(id·cs·court·seq) 포함. 기존 필드 유지.

- [ ] **Step 1: Write the failing test** — `_listings_payload`가 court listing에 대해 `thumbnail_url`·`detail_link` 키를 포함하는지(목 store/snapshot 주입). 기존 `test_web_server.py` 패턴 따라 작성.
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** — listing 직렬화 루프에서 court·thumbnail_path 있으면 `thumbnail_url=f"/api/photo?path={...}"`, `detail_link={"id":identity,"cs":cs_no,"court":cort_ofc_cd,"seq":gds_seq}` 추가.
- [ ] **Step 4: Run → PASS**
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/web_server.py tests/test_web_server.py
git commit -m "feat: 목록 payload에 썸네일·상세링크·권리태그"
```

---

## Task 11: 프런트 — 풍부한 게시판 카드 (v2 샘플 이식)

**Files:**
- Modify: `web/app.js`, `web/styles.css`
- 참고(이식 원본): `../부동산매물 자동 검색v2/sample/index.html` (승인된 카드 마크업/CSS/JS)

**Interfaces:**
- Consumes: `/api/listings`의 `thumbnail_url`·`photo_count`·`incumbrance_tags`·`detail_link`.

- [ ] **Step 1: 샘플 카드 렌더 함수 이식** — 샘플 `index.html`의 `.card` 마크업·`won()/pyeong()/dday()/fitLabel()` 헬퍼·`.card`/`.thumb`/`.fit`/`.drop`/`.tg` CSS를 `app.js`/`styles.css`로 옮긴다. 썸네일 `src`는 `listing.thumbnail_url || placeholder`, 권리태그는 `listing.incumbrance_tags`, 클릭 시 `listing.detail_link` 보유하면 `openDetail(link)` 호출.
- [ ] **Step 2: 로컬 구동 확인**

```bash
python -m realestate_alert serve-web --config config.local.json --port 8765
```
브라우저 `http://127.0.0.1:8765/` → 경매 카드에 썸네일/하락률/권리태그/D-day 표시.

- [ ] **Step 3: 스크린샷 회귀** — 샘플 `01-board.jpeg`와 시각 동등 확인.
- [ ] **Step 4: Commit**

```bash
git add web/app.js web/styles.css
git commit -m "feat: 게시판 카드 풍부화(썸네일·하락률·권리태그)"
```

---

## Task 12: 프런트 — 물건 상세 뷰 (v2 샘플 이식)

**Files:**
- Modify: `web/app.js`, `web/styles.css`, `web/index.html`(모달 컨테이너)

- [ ] **Step 1: 상세 모달 이식** — 샘플의 `openDetail()`/`.modal`/`.two`(min-width:0 포함)/갤러리/기본내역/가격/권리분석/병원적합/주변의료/기일/현황 마크업·CSS를 이식. 데이터 출처를 `fetch('/api/listing/detail?id=...&cs=...&court=...&seq=...')`로 변경(샘플의 인라인 DETAIL 대신).
- [ ] **Step 2: 실거래·심평원 연결** — 가격 패널 실거래는 기존 `market_price`/verify 결과, 주변의료는 기존 `medical_nearby`(`/api/...`) 호출로 채움.
- [ ] **Step 3: 로컬 확인** — 카드 클릭 → 사진 갤러리·현황·기일·권리분석 표시(샘플 `02-detail.jpeg`/`03-hyunhwang.jpeg` 동등).
- [ ] **Step 4: Commit**

```bash
git add web/app.js web/styles.css web/index.html
git commit -m "feat: 물건 상세 뷰(사진·현황·기일·권리·실거래·심평원)"
```

---

## Task 13: 프런트 — 월별 캘린더 뷰 (v2 샘플 이식)

**Files:**
- Modify: `web/app.js`, `web/styles.css`, `web/index.html`

- [ ] **Step 1: 캘린더 이식** — 샘플의 `renderCal()`/`switchView()`/`.calwrap`/`.calgrid`/`.courtgrid` 이식. 데이터는 `fetch('/api/calendar?ym=...')`로 교체. 날짜 클릭 → 그날 매각 물건 게시판 필터(보드 뷰 전환 + sale_date 필터).
- [ ] **Step 2: 로컬 확인** — "월별일정" → 일자별 건수·법원별 카운트(샘플 `04-calendar.jpeg` 동등).
- [ ] **Step 3: Commit**

```bash
git add web/app.js web/styles.css web/index.html
git commit -m "feat: 월별 경매 캘린더 뷰"
```

---

## Task 14: 수집 연결 — 후보 상세 보강 + config

**Files:**
- Modify: `realestate_alert/service.py`(스캔 후 후보 상세 보강), `config.example.json`/`config.render.json`(court 소스 서울 5법원), `config.local.json`(court 추가)

**Interfaces:**
- Consumes: Task 3·4·5. court 소스 listing 중 **신규 또는 관심**만 상세 보강(전건 금지). 간격 sleep. 실패 흡수.

- [ ] **Step 1: Write the failing test** — `enrich_candidates(listings, store, photo_dir, fetcher, is_candidate)`가 후보만 `upsert_detail` 호출하고 비후보는 건드리지 않음(목 fetcher 호출 횟수 검증).
- [ ] **Step 2: Run → FAIL**
- [ ] **Step 3: Implement** `service.py`에 `enrich_candidates(...)`; `run_once`/스캔 흐름에서 court listing에 한해 호출. config에 `{ "type": "court", "court": "서울남부지방법원" }` 등 추가.
- [ ] **Step 4: Run → PASS** + 전체 회귀 `python -m unittest`
- [ ] **Step 5: Commit**

```bash
git add realestate_alert/service.py config.example.json config.render.json config.local.json tests/test_service.py
git commit -m "feat: 스캔 시 병원 후보 상세 보강(신규/관심 한정)"
```

---

## Task 15: 통합 검증 + 회귀 + 배포 준비

**Files:** 없음(검증) / `README.md`(엔드포인트·키 안내 갱신)

- [ ] **Step 1: 전체 테스트** `python -m unittest` — 전부 PASS.
- [ ] **Step 2: 라이브 스모크** — 실제 1물건(2024타경58264) 상세 1회 호출되어 사진 저장·상세 표시되는지 로컬 확인(간격·캐시 동작).
- [ ] **Step 3: 회귀 체크리스트** — 매물장·체크리스트·verify·리포트·지도 동작 유지.
- [ ] **Step 4: README 갱신** — 신규 엔드포인트(`/api/listing/detail`·`/api/photo`·`/api/calendar`)·Pillow 의존성·사진 디렉토리 정책 기술.
- [ ] **Step 5: Commit + PR**

```bash
git add README.md
git commit -m "docs: §1 엔드포인트·의존성 안내 갱신"
git push -u origin feat/court-detail-board-calendar
gh pr create --fill --base main
```

---

## Self-Review

**1. Spec 커버리지:** §3 데이터소스→Task 2·3·6 / §4 모델→Task 1·5 / §5 수집기→Task 2·3·6 / §6 사진→Task 4·8 / §7 웹→Task 11·12·13 / §8 API→Task 7·8·9·10 / §9 재사용→Task 12 / §11 테스트→전 태스크 / §13 리스크(신규/관심 한정·캐시·압축)→Task 14·7·9·4. 누락 없음.

**2. 플레이스홀더:** 백엔드 태스크(1–10·14)는 완전 코드. 프런트 태스크(11–13)는 승인된 샘플 파일을 원본으로 명시하고 데이터소스 치환점을 구체화 — "샘플의 X를 이식, fetch로 교체"로 행동 가능. Task 10·14의 테스트는 기존 `test_web_server.py`/`test_service.py` 패턴 참조로 지정.

**3. 타입 일관성:** `Photo(file,dvs,seq)`·`BidEvent(date,low,result)`·`AuctionDetail` 필드명이 Task 1 정의와 Task 3 파서·Task 7 직렬화에서 동일. `cs_no/cort_ofc_cd/gds_seq`가 Task 2(생성)→Task 7(소비) 일치. `_photo_dir`·`safe_photo_path`·`build_detail_payload`·`build_calendar_payload` 시그니처가 Task 7·8·9에서 일관.

## Notes
- 프런트 3태스크는 단위테스트보다 **로컬 구동 + 스크린샷 회귀**(승인 샘플 대비)가 신호가 큼.
- 사진 비용: 기본 후보 한정·압축. 더 줄이려면 `PHOTO_STORE_MODE=thumb_only`(썸네일 1장만 저장, 갤러리는 상세 조회 시 on-demand) 옵션을 Task 4/7에 추후 추가 가능(YAGNI — 현재 미구현).
