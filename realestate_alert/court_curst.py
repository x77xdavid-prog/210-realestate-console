"""법원경매 현황조사서(임대차관계조사서) 구조화 데이터.

courtauction 상세의 '현황조사서' 버튼은 PDF가 아니라 구조화 JSON을 돌려준다
(B1 추가 역공학). `selectCurstExmndc.on` 한 번으로 점유자·임차인·점유관계가 나온다.

  index.on (쿠키) → POST /pgj/pgj15B/selectCurstExmndc.on
    headers: sc-userid=NONUSER, submissionid=...selectCurstExmn
    body {dma_srchCurstExmn:{cortOfcCd, csNo, auctnInfOriginDvsCd:"2", ordTsCnt:""}}
  → data.dlt_ordTsLserLtn  : 점유자/임차인별(이름·전입·보증금·차임·점유·확정 등)
    data.dlt_ordTsRlet      : 물건별 점유관계(점유내용·임차인수·면적)
    data.dma_curstExmnMngInf: 조사 관리정보(송달/조사일시)

orvParam·상세 호출이 필요 없어 매각물건명세서 딥링크보다 단순하다. csNo는
내부형식(20080130025092)·사용자형식(2008타경25092) 모두 동작.
"""

from __future__ import annotations

import json
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Callable

from realestate_alert.court_documents import BASE_URL, INDEX_URL, REFERER, _UA

CURST_URL = f"{BASE_URL}/pgj/pgj15B/selectCurstExmndc.on"
CURST_SUBMISSION = "mf_wfm_mainFrame_curstExmndcPopUp_wframe_sbm_selectCurstExmn"
TIMEOUT = 20

CurstFetcher = Callable[[dict[str, Any]], str]


def build_curst_body(cs_no: str, cort_ofc_cd: str) -> dict[str, Any]:
    return {
        "dma_srchCurstExmn": {
            "cortOfcCd": cort_ofc_cd,
            "csNo": cs_no,
            "auctnInfOriginDvsCd": "2",
            "ordTsCnt": "",
        }
    }


def _clean(value: Any) -> str:
    text = ("" if value is None else str(value)).strip()
    return "" if text in ("-", "-.") else text


def parse_curst(payload: dict[str, Any]) -> dict[str, Any]:
    """현황조사서 응답 → {tenants, occupancy, survey}. 빈 데이터는 빈 튜플."""
    data = payload.get("data") or {}
    mng = data.get("dma_curstExmnMngInf") or {}

    tenants: list[dict[str, str]] = []
    for t in data.get("dlt_ordTsLserLtn") or []:
        rec = {
            "name": _clean(t.get("intrpsNm")),
            "address": _clean(t.get("objctDtlAddr")),
            "usage": _clean(t.get("lesUsgDts")),
            "deposit": _clean(t.get("lesDposDts")),
            "rent": _clean(t.get("mmrntAmtDts")),
            "move_in": _clean(t.get("mvinDtlCtt")),
            "confirm": _clean(t.get("rgstryCrtcpCfmtnCtt")),
            "part": _clean(t.get("lesPartCtt")),
            "possession": _clean(t.get("gdsPossCtt")),
            "note": _clean(t.get("lesDtsRmk")),
        }
        if rec["name"] or any(
            rec[k] for k in ("deposit", "rent", "move_in", "part", "possession")
        ):
            tenants.append(rec)

    occupancy: list[dict[str, Any]] = []
    for r in data.get("dlt_ordTsRlet") or []:
        item = {
            "address": _clean(r.get("rprsLtnoAddr")),
            "area": _clean(r.get("objctArDts")),
            "tenant_count": r.get("lesCnt"),
            "possession": _clean(r.get("gdsPossCtt")),
            "note": _clean(r.get("rletLstRmk")),
        }
        if item["address"] or item["possession"] or item["note"]:
            occupancy.append(item)

    survey = {
        "sent_date": _clean(mng.get("exmndcSndngYmd")) or None,
        "received_date": _clean(mng.get("exmndcRcptnYmd")) or None,
        "exam_dates": _clean(mng.get("exmnDtDts")) or None,
    }
    return {"tenants": tenants, "occupancy": occupancy, "survey": survey}


def fetch_tenants(
    cs_no: str, cort_ofc_cd: str, fetcher: CurstFetcher | None = None
) -> dict[str, Any]:
    """현황조사서 임대차/점유 데이터를 가져와 파싱한다. 실패는 흡수하고 빈 구조."""
    body = build_curst_body(cs_no, cort_ofc_cd)
    try:
        raw = (fetcher or _live_curst)(body)
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — 외부 호출·파싱 실패 흡수
        print(f"[court-curst] 현황조사서 조회 실패 ({cort_ofc_cd} {cs_no}): {exc}")
        return {"tenants": [], "occupancy": [], "survey": {}}
    return parse_curst(payload)


def _live_curst(body: dict[str, Any]) -> str:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    opener.open(
        urllib.request.Request(
            INDEX_URL,
            headers={
                "User-Agent": _UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                "Upgrade-Insecure-Requests": "1",
            },
        ),
        timeout=TIMEOUT,
    ).read(1024)
    req = urllib.request.Request(
        CURST_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "User-Agent": _UA,
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": REFERER,
            "sc-userid": "NONUSER",
            "submissionid": CURST_SUBMISSION,
        },
    )
    with opener.open(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")
