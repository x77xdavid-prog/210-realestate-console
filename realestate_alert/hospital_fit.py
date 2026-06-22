"""매물의 '병원(정형외과) 적합도'를 판정한다.

기본은 소스가 주는 용도 정보(usage·title) 키워드로 즉시 판정하되(추가 API 호출 없음),
공공데이터(건축물대장 주용도·용도지역)가 있으면 인자로 받아 판정을 정밀화한다.

판정은 4단계 level + 0~100 fit_score:
- open  : 개원 가능 — 상가·근린생활시설 등 기존 건물에 의원 입점 가능
- build : 신축 가능 — 대지·토지 (의료시설 신축 후보)
- check : 확인 필요 — 주거용(주택·빌라)·용도 불명 → 1층 전환/철거 신축 검토
- unfit : 부적합 — 전·답·임야·도로 등 (병원 건축 불가)

fit_score 는 추천 랭킹의 입력으로도 쓰인다(클수록 적합).
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
# 의원/병원 입점 가능한 상업·근린 용도.
# "근생"을 포함해 "1종근생"·"제2종근생" 등 약어 변이를 부분일치로 흡수한다.
_COMMERCIAL = ("근린", "근생", "상가", "상업", "업무", "점포", "사무", "판매", "의료", "병원", "의원")
# 신축 후보가 되는 토지 용도
_BUILDABLE_LAND = ("대지", "나대지", "잡종지", "토지", "공장용지", "창고용지")
# 주거용 — 확인 필요(1층 전환/철거 신축 검토)
_RESIDENTIAL = ("주택", "다세대", "빌라", "연립", "아파트", "오피스텔", "주거", "도시형생활", "단독", "다가구")

# 건축물대장 주용도(main_purpose) → 적합 경향
_PURPOSE_OPEN = ("근린생활", "근생", "의료", "업무", "판매", "상가", "점포", "사무")
_PURPOSE_RESIDENTIAL = ("주택", "공동주택", "단독", "다세대", "다가구", "연립", "아파트", "주거", "오피스텔")
_PURPOSE_BUILD = ("공장", "창고")

_LABELS = {
    "open": "개원 가능",
    "build": "신축 가능",
    "check": "확인 필요",
    "unfit": "부적합",
}
# level 기본 점수 (fit_score 산출의 베이스)
_LEVEL_BASE = {"open": 75, "build": 55, "check": 35, "unfit": 5}
# level별 점수 밴드 — 보정(용도지역·주용도)을 적용해도 레벨 간 순서(open>build>check>unfit)가
# 뒤집히지 않도록 각 레벨을 겹치지 않는 구간에 가둔다.
_LEVEL_BAND = {"open": (60, 100), "build": (40, 59), "check": (15, 39), "unfit": (0, 14)}


def _is_unfit(usage: str, title: str) -> bool:
    if usage in _UNFIT_EXACT:
        return True
    if any(f"({term})" in title for term in _UNFIT_EXACT):
        return True
    return any(term in usage or term in title for term in _UNFIT_CONTAINS)


def _purpose_level(main_purpose: str | None) -> str | None:
    """건축물대장 주용도를 적합 level 로 매핑한다(해당 없으면 None)."""
    if not main_purpose:
        return None
    text = main_purpose.strip()
    if not text:
        return None
    if any(term in text for term in _PURPOSE_OPEN):
        return "open"
    if any(term in text for term in _PURPOSE_RESIDENTIAL):
        return "check"
    if any(term in text for term in _PURPOSE_BUILD):
        return "build"
    return None


def _zoning_bonus(zoning: str | None) -> int:
    """용도지역에 따른 fit_score 보정값. 순서 주의(전용주거를 일반주거보다 먼저 검사)."""
    if not zoning:
        return 0
    z = zoning.strip()
    if "상업" in z:
        return 15
    if "준주거" in z:
        return 15
    if "전용주거" in z:
        return -10
    if "주거" in z:  # 일반주거 등
        return 5
    return 0


def _purpose_bonus(main_purpose: str | None) -> int:
    level = _purpose_level(main_purpose)
    if level == "open":
        return 10
    if level == "check":
        return -5
    return 0


def classify(
    listing: Listing,
    *,
    zoning: str | None = None,
    main_purpose: str | None = None,
) -> dict[str, object]:
    """매물을 병원 적합도 4단계로 분류한다.

    {'level', 'label', 'reason', 'fit_score'} 반환. zoning·main_purpose 가 주어지면
    (공공데이터 검증을 거친 매물) 판정과 점수를 정밀화한다.
    """
    usage = (listing.usage or "").strip()
    title = listing.title or ""
    combined = f"{usage} {title}"
    purpose_level = _purpose_level(main_purpose)

    level, reason = _decide_level(listing, usage, title, combined, purpose_level)

    score = _LEVEL_BASE[level]
    if level != "unfit":
        score += _zoning_bonus(zoning) + _purpose_bonus(main_purpose)
    low, high = _LEVEL_BAND[level]
    score = max(low, min(high, score))  # 레벨 밴드로 가둬 레벨 간 순서를 보장

    return {"level": level, "label": _LABELS[level], "reason": reason, "fit_score": int(score)}


def _decide_level(
    listing: Listing,
    usage: str,
    title: str,
    combined: str,
    purpose_level: str | None,
) -> tuple[str, str]:
    if _is_unfit(usage, title):
        return "unfit", "농지·임야·도로 등 병원 건축 불가"
    if purpose_level == "open":
        return "open", "건축물대장 주용도 근린생활·의료 — 의원 개원 가능"
    if any(keyword in combined for keyword in _COMMERCIAL):
        return "open", "상가·근린생활시설 — 의원 개원 가능"
    if purpose_level == "check":
        return "check", "건축물대장 주용도 주거 — 1층 전환·철거 후 신축 검토"
    if listing.property_type == "land" or any(keyword in combined for keyword in _BUILDABLE_LAND):
        return "build", "토지·대지 — 병원 신축 후보 (용도지역 확인)"
    if purpose_level == "build":
        return "build", "공장·창고 — 철거 후 신축 검토"
    if any(keyword in combined for keyword in _RESIDENTIAL):
        return "check", "주거용 — 1층 전환·철거 후 신축 검토"
    return "check", "용도 정보 부족 — 공공데이터 검증 필요"
