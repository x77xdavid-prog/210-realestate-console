from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable
from xml.etree import ElementTree

DATA_GO_KR_KEY_ENV = "DATA_GO_KR_API_KEY"
VWORLD_KEY_ENV = "VWORLD_API_KEY"
REQUEST_TIMEOUT_SECONDS = 15
# 게이트웨이 일시 오류(502/503/504)·네트워크 오류는 짧게 재시도한다 — VWorld·data.go.kr
# 게이트웨이가 간헐적으로 502를 돌려줘 단발성 실패가 사용자에게 노출되던 문제 완화.
RETRY_STATUSES = frozenset({502, 503, 504})
HTTP_MAX_RETRIES = 2  # 총 시도 = 3회
HTTP_RETRY_BACKOFF_SECONDS = 0.6

# fetcher(url) -> 응답 본문 문자열. 테스트에서 가짜 응답 주입에 사용한다.
Fetcher = Callable[[str], str]


class PublicDataError(RuntimeError):
    """공공 API 호출/파싱 실패."""


class MissingApiKeyError(PublicDataError):
    def __init__(self, env_name: str, guide: str):
        super().__init__(f"환경 변수 {env_name}가 설정되지 않았습니다. {guide}")
        self.env_name = env_name


def require_key(env_name: str, guide: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise MissingApiKeyError(env_name, guide)
    return value


def data_go_kr_key() -> str:
    return require_key(
        DATA_GO_KR_KEY_ENV,
        "공공데이터포털(data.go.kr)에서 활용신청 후 발급받은 일반 인증키(Decoding)를 설정하세요.",
    )


def vworld_key() -> str:
    return require_key(
        VWORLD_KEY_ENV,
        "브이월드(vworld.kr) 회원가입 후 오픈API 인증키를 발급받아 설정하세요.",
    )


def http_get(url: str, accept: str | None = None) -> str:
    headers = {"User-Agent": "realestate-alert/1.0"}
    if accept:
        # 건축HUB 등 일부 게이트웨이는 Accept 헤더가 없으면 빈 본문(200)을 반환한다.
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    for attempt in range(HTTP_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as error:
            # 5xx 게이트웨이 오류만 재시도. 4xx(키·요청 오류)는 즉시 실패.
            if error.code in RETRY_STATUSES and attempt < HTTP_MAX_RETRIES:
                time.sleep(HTTP_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise PublicDataError(f"공공 API 호출 실패: {url.split('?')[0]} ({error})") from error
        except urllib.error.URLError as error:
            # 타임아웃·연결 오류 등 네트워크 일시 오류도 재시도.
            if attempt < HTTP_MAX_RETRIES:
                time.sleep(HTTP_RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
            raise PublicDataError(f"공공 API 호출 실패: {url.split('?')[0]} ({error})") from error
    raise PublicDataError(f"공공 API 호출 실패: {url.split('?')[0]} (재시도 초과)")


def xml_fetcher(url: str) -> str:
    return http_get(url, accept="application/xml")


def json_fetcher(url: str) -> str:
    return http_get(url, accept="application/json")


def build_url(base: str, params: dict[str, str]) -> str:
    return f"{base}?{urllib.parse.urlencode(params)}"


def parse_xml_items(body: str) -> list[dict[str, str]]:
    """공공데이터포털 표준 XML 응답에서 <item> 목록을 dict로 변환한다."""
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        raise PublicDataError(f"XML 응답 파싱 실패: {error}") from error
    _raise_on_error_header(root)
    return [
        {child.tag: (child.text or "").strip() for child in item}
        for item in root.iter("item")
    ]


def _raise_on_error_header(root: ElementTree.Element) -> None:
    result_code = root.findtext(".//resultCode")
    if result_code and result_code not in ("00", "000"):
        message = root.findtext(".//resultMsg") or "알 수 없는 오류"
        raise PublicDataError(f"공공 API 오류 응답: [{result_code}] {message}")


def find_dicts_with_key(payload: Any, key: str) -> list[dict[str, Any]]:
    """JSON 트리를 순회하며 특정 키를 가진 dict를 모두 수집한다.

    V-World ned 계열 API는 래퍼 키 이름이 서비스마다 달라 방어적으로 파싱한다.
    """
    found: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        if key in payload:
            found.append(payload)
        for value in payload.values():
            found.extend(find_dicts_with_key(value, key))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(find_dicts_with_key(item, key))
    return found


def parse_json(body: str) -> Any:
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise PublicDataError(f"JSON 응답 파싱 실패: {error}") from error


def to_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = str(value).replace(",", "").strip()
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def to_int(value: str | None) -> int | None:
    number = to_float(value)
    return None if number is None else int(number)
