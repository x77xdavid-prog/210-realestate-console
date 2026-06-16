"""매물의 '병원 적합도'를 소스가 주는 용도 정보로 즉시 판정한다(추가 API 호출 없음).

판정은 4단계:
- open  : 개원 가능 — 상가·근린생활시설 등 기존 건물에 의원 입점 가능
- build : 신축 가능 — 대지·토지 (의료시설 신축 후보)
- check : 확인 필요 — 주거용(주택·빌라)·용도 불명 → 1층 전환/철거 신축 검토
- unfit : 부적합 — 전·답·임야·도로 등 (병원 건축 불가)

정밀 판정(용도지역·건축물 용도)은 '공공데이터 검증'이 보완한다.
"""

from __future__ import annotations

from realestate_alert.models import Listing

# 농지·임야·맹지류 — 병원 건축 불가. 짧은 용어(전/답)는 오탐을 막으려 정확히 비교한다.
_UNFIT_EXACT = {
    "전", "답", "과수원", "임야", "목장용지", "도로", "구거", "하천", "제방",
    "묘지", "유지", "광천지", "염전", "양어장", "수도용지", "사적지", "잡종지및기타",
}
# 제목/용도에 부분일치만으로도 부적합으로 볼 수 있는 용어 (농지·임야 + 부동산 아닌 동산)
_UNFIT_CONTAINS = (
    "임야", "과수원", "목장", "구거", "하천", "제방", "묘지", "염전", "양어장", "농지",
    "자동차", "차량", "선박", "중기", "건설기계", "항공기",
)
# 의원/병원 입점 가능한 상업·근린 용도 ("근린"은 근린시설·근린상가·근린생활·근린주택을 모두 포함)
_COMMERCIAL = ("근린", "상가", "상업", "업무", "점포", "사무", "판매", "의료", "병원", "의원")
# 신축 후보가 되는 토지 용도
_BUILDABLE_LAND = ("대지", "나대지", "잡종지", "토지", "공장용지", "창고용지")
# 주거용 — 확인 필요(1층 전환/철거 신축 검토)
_RESIDENTIAL = ("주택", "다세대", "빌라", "연립", "아파트", "오피스텔", "주거", "도시형생활", "단독", "다가구")

_LABELS = {
    "open": "개원 가능",
    "build": "신축 가능",
    "check": "확인 필요",
    "unfit": "부적합",
}


def _is_unfit(usage: str, title: str) -> bool:
    if usage in _UNFIT_EXACT:
        return True
    if any(f"({term})" in title for term in _UNFIT_EXACT):
        return True
    return any(term in usage or term in title for term in _UNFIT_CONTAINS)


def classify(listing: Listing) -> dict[str, str]:
    """매물을 병원 적합도 4단계로 분류한다. {'level', 'label', 'reason'} 반환."""
    usage = (listing.usage or "").strip()
    title = listing.title or ""
    combined = f"{usage} {title}"

    if _is_unfit(usage, title):
        return _result("unfit", "농지·임야·도로 등 병원 건축 불가")
    if any(keyword in combined for keyword in _COMMERCIAL):
        return _result("open", "상가·근린생활시설 — 의원 개원 가능")
    if listing.property_type == "land" or any(keyword in combined for keyword in _BUILDABLE_LAND):
        return _result("build", "토지·대지 — 병원 신축 후보 (용도지역 확인)")
    if any(keyword in combined for keyword in _RESIDENTIAL):
        return _result("check", "주거용 — 1층 전환·철거 후 신축 검토")
    return _result("check", "용도 정보 부족 — 공공데이터 검증 필요")


def _result(level: str, reason: str) -> dict[str, str]:
    return {"level": level, "label": _LABELS[level], "reason": reason}
