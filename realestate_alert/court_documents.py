"""법원경매 전자문서(매각물건명세서 등) 뷰어 딥링크 생성.

courtauction 상세 페이지의 '매각물건명세서' 버튼은 다음 흐름으로 ecfs 전자문서
뷰어 URL을 만든다(B1 역공학 → briefs/BL0-encparam.md):

  같은 세션:
    1) index.on (쿠키)
    2) selectAuctnCsSrchRslt.on (상세) → dspslGdsDxdyInfo.orvParam / dspslGdsSpcfcEcdocId
    3) insertDspslGdsSpecArtcWdrwInf.on (sc-userid=NONUSER, sc-pgmid=PGJ15BM01,
       submissionid=...) → {url, encParam}
    4) viewer = url + '?paramData=' + base64({encParam, pspTkn:NA, pspSid:NA})

encParam은 서버가 생성하므로 클라이언트 암호화 재현이 필요 없다. 단 orvParam이
상세를 조회한 세션에 묶이므로 상세 조회와 문서 로그 호출을 같은 세션에서 한다.
"""

from __future__ import annotations

import base64
import json
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Protocol

from realestate_alert.court_auction_detail import build_detail_body

BASE_URL = "https://www.courtauction.go.kr"
INDEX_URL = f"{BASE_URL}/pgj/index.on"
DETAIL_URL = f"{BASE_URL}/pgj/pgj15B/selectAuctnCsSrchRslt.on"
SALE_SPEC_LOG_URL = f"{BASE_URL}/pgj/pgj15B/insertDspslGdsSpecArtcWdrwInf.on"
REFERER = f"{INDEX_URL}?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml"
SALE_SPEC_SUBMISSION = "mf_wfm_mainFrame_sbm_insertDspslGdsSpecLogInfo"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)
TIMEOUT = 20


class DocSession(Protocol):
    """상세 + 문서로그 호출을 한 세션으로 묶는 추상화 (테스트 주입용)."""

    def post_detail(self, body: dict[str, Any]) -> dict[str, Any]: ...

    def post_sale_spec_log(self, body: dict[str, Any]) -> dict[str, Any]: ...


def extract_doc_params(detail_payload: dict[str, Any]) -> tuple[str, str]:
    """상세 응답에서 (orvParam, dspslGdsSpcfcEcdocId)를 뽑는다. 없으면 빈 문자열."""
    dx = (
        ((detail_payload.get("data") or {}).get("dma_result") or {}).get("dspslGdsDxdyInfo")
        or {}
    )
    return str(dx.get("orvParam") or ""), str(dx.get("dspslGdsSpcfcEcdocId") or "")


def build_sale_spec_log_body(
    cs_no: str, cort_ofc_cd: str, gds_seq: str, orv_param: str, ecdoc_id: str
) -> dict[str, Any]:
    return {
        "dma_dspslGdsSpecLog": {
            "cortOfcCd": cort_ofc_cd,
            "csNo": cs_no,
            "dspslGdsSeq": _as_int(gds_seq),
            "orvParam": orv_param,
            "dspslGdsSpcfcEcdocId": ecdoc_id,
            "cortAuctnMbrsId": "NONUSER",
            "docFlag": "1",
            "dspslDxdyPbancEcdocId": "",
        }
    }


def build_viewer_url(base_url: str, enc_param: str) -> str:
    """ecfs 뷰어 base + encParam → 최종 딥링크 URL."""
    param_data = base64.b64encode(
        json.dumps(
            {"encParam": enc_param, "pspTkn": "NA", "pspSid": "NA"},
            ensure_ascii=False,
        ).encode("utf-8")
    ).decode("ascii")
    return f"{base_url}?paramData={param_data}"


def sale_spec_viewer_url(
    cs_no: str, cort_ofc_cd: str, gds_seq: str, session: DocSession | None = None
) -> str | None:
    """매각물건명세서 전자문서 뷰어 딥링크. 데이터·네트워크 실패는 흡수하고 None."""
    try:
        sess = session or _LiveSession()
        detail = sess.post_detail(build_detail_body(cs_no, cort_ofc_cd, gds_seq))
        orv_param, ecdoc_id = extract_doc_params(detail)
        if not orv_param or not ecdoc_id:
            return None
        log = sess.post_sale_spec_log(
            build_sale_spec_log_body(cs_no, cort_ofc_cd, gds_seq, orv_param, ecdoc_id)
        )
        info = (log.get("data") or {}).get("dma_dspslSpcfcInfo") or {}
        enc = info.get("encParam")
        url = info.get("url")
        if not enc or not url:
            return None
        return build_viewer_url(url, enc)
    except Exception:  # noqa: BLE001 — 외부 호출 실패는 전부 흡수
        return None


def _as_int(value: Any) -> Any:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return value


class _LiveSession:
    """courtauction 라이브 세션 — index 쿠키 후 상세/문서로그를 같은 opener로 호출."""

    def __init__(self) -> None:
        self._jar = CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar)
        )
        self._opener.open(
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

    def post_detail(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post(DETAIL_URL, body, {"sc-userid": "SYSTEM"})

    def post_sale_spec_log(self, body: dict[str, Any]) -> dict[str, Any]:
        return self._post(
            SALE_SPEC_LOG_URL,
            body,
            {
                "sc-userid": "NONUSER",
                "sc-pgmid": "PGJ15BM01",
                "submissionid": SALE_SPEC_SUBMISSION,
            },
        )

    def _post(self, url: str, body: dict[str, Any], extra: dict[str, str]) -> dict[str, Any]:
        headers = {
            "User-Agent": _UA,
            "Accept": "application/json",
            "Content-Type": "application/json;charset=UTF-8",
            "Referer": REFERER,
        }
        headers.update(extra)
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
        with self._opener.open(req, timeout=TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
