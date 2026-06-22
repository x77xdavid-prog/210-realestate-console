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
