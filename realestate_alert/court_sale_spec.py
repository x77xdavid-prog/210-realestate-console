"""매각물건명세서 PDF 텍스트 추출 + 파싱 (대항력·배당·말소기준).

현황조사서(court_curst)에 없는 **법원 판단** 항목 — 최선순위 설정일(말소기준권리),
임차인별 확정일자·배당요구, 대항력/인수 비고 — 은 매각물건명세서 PDF에만 있다.
이 PDF는 전자문서 뷰어(ecfs)+StreamDocs로 서빙되며, 텍스트 레이어를 서버에서
추출할 수 있다(B-full 역공학):

  court_documents.sale_spec_doc_info → {viewer_base, enc_param, ecdoc_id, cortCd}
  ecfs: GET 뷰어(쿠키) → POST selectDocVwrInf.on(encParam)
        → POST getPdf.on(ecdocId·csNo·cortCd) → {streamdocsId, accessToken}
  StreamDocs: GET /documents/{id}/texts/{page}  (Authorization: Access-Token)
        → 텍스트런(text+rect) → y밴드로 라인 재구성

파싱은 키워드 앵커 기반(배당요구종기/최선순위/임차인 성명/<비고>)으로 최대한
견고하게 하되, 표가 다중라인으로 wrap되므로 임차인은 '성명 + 해당 라인 전문'으로
보수적으로 추출하고 비고는 원문 발췌로 제공한다(사용자는 PDF 딥링크로 대조).
"""

from __future__ import annotations

import gzip
import json
import re
import urllib.request
from collections import defaultdict
from http.cookiejar import CookieJar
from typing import Any, Callable

from realestate_alert.court_documents import _UA, build_viewer_url, sale_spec_doc_info

ECFS_BASE = "https://ecfs.scourt.go.kr"
PVO_BASE = "https://pvo.scourt.go.kr"
VWR_INF_URL = f"{ECFS_BASE}/sgvo/sgvomain/selectDocVwrInf.on"
GET_PDF_URL = f"{ECFS_BASE}/sgvo/sgvomain/getPdf.on"
TIMEOUT = 25
MAX_PAGES = 12

LinesFetcher = Callable[[str, str, str], list[str]]

_DATE = r"\d{4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}"
_NAME_ROW = re.compile(r"^[가-힣]{2,4}\s")


def _cort_cd(cort_ofc_cd: str) -> str:
    """courtauction 법원코드(B000210) → ecfs cortCd(000210)."""
    return cort_ofc_cd[1:] if cort_ofc_cd[:1].isalpha() else cort_ofc_cd


# ── 파싱 (순수) ────────────────────────────────────────────────────────────────


def _norm_date(text: str) -> str:
    return re.sub(r"\s+", "", text).rstrip(".") if text else ""


def parse_sale_spec(lines: list[str]) -> dict[str, Any]:
    """재구성된 라인 → {dividend_deadline, priority, tenants, notes, has_data}."""
    clean = [ln.strip() for ln in lines if ln and ln.strip()]
    blob = "\n".join(clean)

    deadline = None
    m = re.search(r"배당요구종기\D*?(" + _DATE + r")", blob)
    if m:
        deadline = _norm_date(m.group(1))

    # 최선순위 설정(말소기준): 상단 블록의 "토지/건물 : 날짜 (근저당 등)" 라인
    priority: list[str] = []
    for ln in clean:
        if "점유자" in ln:  # 임차인 표 시작 전까지만
            break
        pm = re.search(r"(토지|집합건물|건물|토지및건물)\s*[:：]\s*(" + _DATE + r")", ln)
        if pm:
            priority.append(f"{pm.group(1)} {_norm_date(pm.group(2))}")

    # 임차인 표 영역: 헤더(확정일자/신청일자) 이후 ~ <비고> 전.
    # 표 헤더 잔여조각을 거르려 날짜/금액/미상이 있는 성명行만 임차인으로 본다.
    start = _first_index(clean, lambda s: "신청일자" in s or "확정일자" in s)
    note_idx = _first_index(clean, lambda s: s.startswith("<비고>") or s == "비고란")
    region = clean[(start + 1 if start is not None else 0): (note_idx if note_idx is not None else len(clean))]
    _HDR_WORDS = ("성명", "성  명", "점유자", "점유정보", "점유의", "보 증", "전입신고", "외국인")
    tenants: list[dict[str, str]] = []
    for ln in region:
        if not _NAME_ROW.match(ln) or ln.startswith(_HDR_WORDS):
            continue
        rest = ln[len(ln.split()[0]):].strip()
        if not (re.search(_DATE, rest) or "미상" in rest or re.search(r"\d+\s*만원|원", rest)):
            continue
        tenants.append({"name": ln.split()[0], "detail": re.sub(r"\s{2,}", " ", rest)})

    # 비고: <비고> ~ '부동산의 표시' 전. 표준 대항력 안내문(보일러플레이트)은 제외.
    _BOILER = ("최선순위 설정일자보다", "대항력과 우선변제권", "보증금 전액에 관하여",
               "배당받지 못한", "인수되게 됨을", "주의하시기", "수 있고", "경우에는 배당")
    notes: list[str] = []
    if note_idx is not None:
        for ln in clean[note_idx + 1:]:
            if ln.startswith(("부동산의 표시", "매각으로 소멸", "매각에 따라", "[물건", "감정평가액")):
                break
            if ln.startswith(("등기된 부동산", "전입신고일자", "※")) or any(b in ln for b in _BOILER):
                continue
            if "2: 매각으로" in ln or ln.startswith("2:"):
                continue
            notes.append(re.sub(r"\s{2,}", " ", ln))

    has_data = bool(deadline or priority or tenants or notes)
    return {
        "dividend_deadline": deadline,
        "priority": priority,
        "tenants": tenants,
        "notes": notes,
        "has_data": has_data,
    }


def _first_index(items: list[str], pred: Callable[[str], bool]) -> int | None:
    for i, it in enumerate(items):
        if pred(it):
            return i
    return None


def fetch_sale_spec(
    cs_no: str, cort_ofc_cd: str, gds_seq: str, lines_fetcher: LinesFetcher | None = None
) -> dict[str, Any]:
    """매각물건명세서 텍스트를 가져와 파싱한다. 실패는 흡수하고 빈 구조."""
    try:
        lines = (lines_fetcher or _live_sale_spec_lines)(cs_no, cort_ofc_cd, gds_seq)
    except Exception as exc:  # noqa: BLE001
        print(f"[sale-spec] 텍스트 추출 실패 ({cort_ofc_cd} {cs_no}): {exc}")
        return {"dividend_deadline": None, "priority": [], "tenants": [], "notes": [], "has_data": False}
    return parse_sale_spec(lines)


# ── 라이브 ecfs+StreamDocs 흐름 ────────────────────────────────────────────────


def reconstruct_lines(runs: list[dict[str, Any]]) -> list[str]:
    """StreamDocs 텍스트런(text+rect) → 읽기순 라인. y밴드 그룹 후 x정렬."""
    bands: dict[int, list[tuple[float, str]]] = defaultdict(list)
    for run in runs:
        rect = run.get("rect") or []
        if not rect:
            continue
        top = rect[0].get("top")
        left = rect[0].get("left")
        if top is None or left is None:
            continue
        bands[round(top / 3) * 3].append((left, run.get("text", "")))
    lines: list[str] = []
    for top in sorted(bands, reverse=True):  # PDF 좌표는 하단기준 → top 큰 게 위
        line = "".join(text for _, text in sorted(bands[top])).strip()
        if line:
            lines.append(line)
    return lines


def _build_getpdf_body(ecdoc_id: str, cs_no: str, cort_cd: str) -> dict[str, Any]:
    return {
        "dma_srchEdms": {
            "ecdocId": ecdoc_id, "ecdocDtlSeq": "1", "ecdocFileSeq": "", "dcmevdSeq": "",
            "csNo": cs_no, "rdngLimtFileYn": "", "extnlUserYn": "Y", "bubviewerYn": "N",
            "jobKind": "JH", "edmsUsePurpDvsCd": "", "fileEdmsDocId": "", "vwrSoltnDocId": "",
            "rdngLimtScopDvsCd": "06", "pin": "", "urlDvs": "", "searDvs": "",
            "docNm": "매각물건명세서", "userId": "NONUSER", "cortCd": cort_cd,
            "comTaskTypCd": "", "ecdocCrtHstDvsCd": "", "scPgmId": "", "docuStartPageNo": "",
            "docuLstPageNo": "", "docuPageNoYn": "", "csNoR": "", "cortCdR": "",
            "mngrUserId": "", "passFlag": "", "scinMode": "",
        },
        "dma_header": {"SC-Userid": "NONUSER", "SC-Pgmid": "SGVO201", "SC-Token": "NA", "LifeSpan": "", "SID": ""},
        "dma_downloadOtpt": {}, "dma_downloadOtptDcmevd": {},
    }


def _live_sale_spec_lines(cs_no: str, cort_ofc_cd: str, gds_seq: str) -> list[str]:
    info = sale_spec_doc_info(cs_no, cort_ofc_cd, gds_seq)
    if not info:
        return []
    viewer_url = build_viewer_url(info["viewer_base"], info["enc_param"])
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _post(url: str, body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"),
            headers={"User-Agent": _UA, "Accept": "application/json",
                     "Content-Type": "application/json;charset=UTF-8", "Referer": viewer_url,
                     "sc-token": "NA", "sc-pgmid": "SGVO201", "sc-userid": "NONUSER"},
        )
        with opener.open(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    # 1) 뷰어 GET(쿠키) → selectDocVwrInf(encParam) → getPdf
    opener.open(urllib.request.Request(viewer_url, headers={"User-Agent": _UA}), timeout=TIMEOUT).read(200)
    _post(VWR_INF_URL, {"dma_parm": {"encParam": info["enc_param"], "sidParam": "NA"}})
    pdf = _post(GET_PDF_URL, _build_getpdf_body(info["ecdoc_id"], cs_no, _cort_cd(cort_ofc_cd)))
    data = pdf.get("data") or {}
    sid = data.get("streamdocsId")
    token = data.get("accessToken")
    if not sid or not token:
        return []

    # 2) StreamDocs 텍스트 레이어를 페이지별로 (Authorization: Access-Token)
    auth = {"User-Agent": _UA, "Authorization": "Access-Token " + token,
            "Accept": "application/json, text/plain, */*", "Referer": f"{PVO_BASE}/streamdocs/view/sd"}
    try:
        opener.open(urllib.request.Request(f"{PVO_BASE}/streamdocs/v4/documents/{sid}/document", headers=auth), timeout=TIMEOUT).read(50)
    except Exception:  # noqa: BLE001 — document open은 선택적
        pass
    lines: list[str] = []
    for page in range(MAX_PAGES):
        try:
            resp = opener.open(
                urllib.request.Request(f"{PVO_BASE}/streamdocs/v4/documents/{sid}/texts/{page}", headers=auth),
                timeout=TIMEOUT,
            )
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            runs = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 — 페이지 끝(404 등)
            break
        if not runs:
            break
        lines.extend(reconstruct_lines(runs))
    return lines
