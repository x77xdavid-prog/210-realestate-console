"""병원(정형외과) 추천 복합 점수 — 순수 계산 모듈(외부 IO 없음).

가용 신호만 가중·정규화한다(누락 신호는 가중에서 제외해 패널티가 없게). 가중치는
named profile(`WEIGHTS`)로 분리해 향후 다른 과로 확장 가능하게 한다(기본 'ortho').

- baseline_score: 무료 신호(적합도·할인율·입지)만. 전 매물 즉시 계산용.
- enriched_score: 공공데이터 검증 신호(등급·시세·경쟁의원) 추가. 상위 후보용.
"""

from __future__ import annotations

from realestate_alert.models import Listing

# 정형외과 기준 가중치 프로필(합계 1.0). 향후 다른 과는 항목을 추가하면 된다.
WEIGHTS: dict[str, dict[str, float]] = {
    "ortho": {
        "fit": 0.30,         # 적합도(hospital_fit.fit_score)
        "grade": 0.20,       # 체크리스트 등급
        "price": 0.15,       # 시세 대비 저평가
        "competition": 0.15, # 주변 정형외과 경쟁(낮을수록↑)
        "discount": 0.10,    # 경매 할인율
        "location": 0.10,    # 정형외과 입지(주차·연면적·1층·승강기)
    },
}

_GRADE_SUB = {"A": 1.0, "B": 0.75, "C": 0.5, "D": 0.25, "부적합": 0.0}


def composite_score(signals: dict[str, float | None], *, profile: str = "ortho") -> float:
    """가용 신호(0~1)만 가중 평균해 0~100 점수를 낸다. 누락(None) 신호는 제외."""
    weights = WEIGHTS[profile]
    numerator = 0.0
    denominator = 0.0
    for key, weight in weights.items():
        sub = signals.get(key)
        if sub is None:
            continue
        clamped = max(0.0, min(1.0, sub))
        numerator += weight * clamped
        denominator += weight
    if denominator == 0:
        return 0.0
    return round(numerator / denominator * 100, 1)


def _discount_sub(listing: Listing) -> float | None:
    appraisal = listing.appraisal_price
    min_bid = listing.min_bid_price
    if not appraisal or appraisal <= 0 or min_bid is None or min_bid < 0:
        return None
    discount = (appraisal - min_bid) / appraisal
    return max(0.0, min(1.0, discount / 0.5))  # 50% 이상이면 만점


def _price_sub(listing: Listing, market_avg_ppm: float | None) -> float | None:
    if not market_avg_ppm or market_avg_ppm <= 0 or not listing.area_m2:
        return None
    unit_price = listing.min_bid_price or listing.appraisal_price
    if not unit_price or unit_price <= 0:
        return None
    listing_ppm = unit_price / listing.area_m2
    ratio = listing_ppm / market_avg_ppm
    return max(0.0, min(1.0, (1.4 - ratio) / 0.6))  # ≤0.8→1.0, ≥1.4→0.0


def _competition_sub(ortho_count: int | None) -> float | None:
    if ortho_count is None:
        return None
    return {0: 1.0, 1: 0.7, 2: 0.4}.get(ortho_count, 0.1)


def _location_sub(listing: Listing) -> float | None:
    """정형외과 입지(주차·연면적·1층 접근·승강기)를 가용 항목 평균으로 0~1 산출."""
    parts: list[float] = []
    if listing.parking_spaces is not None:
        parts.append(1.0 if listing.parking_spaces >= 5 else 0.5 if listing.parking_spaces >= 1 else 0.0)
    if listing.building_area_m2 is not None:
        area = listing.building_area_m2
        parts.append(1.0 if area >= 200 else 0.5 if area >= 100 else 0.0)
    if listing.floor:
        parts.append(1.0 if "1층" in listing.floor else 0.3)  # 거동 불편 환자 → 1층 유리
    if listing.elevator is not None:
        parts.append(1.0 if listing.elevator else 0.0)
    if not parts:
        return None
    return sum(parts) / len(parts)


def _grade_sub(grade: str | None) -> float | None:
    if grade is None:
        return None
    return _GRADE_SUB.get(grade)


def extract_recommend_signals(report: dict) -> dict:
    """공공데이터 검증 리포트에서 추천 보강 신호를 뽑는다(순수).

    {market_avg_ppm, ortho_count, main_purpose, zoning} — 없으면 None.
    """
    market = report.get("market") or {}
    medical = report.get("medical") or {}
    building = report.get("building") or {}
    land = report.get("land") or {}
    zoning_names = land.get("zoning_names") or []
    return {
        "market_avg_ppm": market.get("avg_price_per_m2"),
        "ortho_count": medical.get("ortho_clinic_count"),
        "main_purpose": building.get("main_purpose"),
        "zoning": ", ".join(zoning_names) if zoning_names else None,
    }


def baseline_score(listing: Listing, fit: dict, *, profile: str = "ortho") -> float:
    """무료 신호(적합도·할인율·입지)만으로 전 매물에 매기는 1차 점수."""
    signals = {
        "fit": (fit.get("fit_score") or 0) / 100,
        "discount": _discount_sub(listing),
        "location": _location_sub(listing),
    }
    return composite_score(signals, profile=profile)


def enriched_score(
    listing: Listing,
    fit: dict,
    *,
    grade: str | None = None,
    market_avg_ppm: float | None = None,
    ortho_count: int | None = None,
    profile: str = "ortho",
) -> float:
    """공공데이터 검증 신호(등급·시세·경쟁의원)를 더한 정밀 점수(상위 후보용)."""
    signals = {
        "fit": (fit.get("fit_score") or 0) / 100,
        "grade": _grade_sub(grade),
        "price": _price_sub(listing, market_avg_ppm),
        "competition": _competition_sub(ortho_count),
        "discount": _discount_sub(listing),
        "location": _location_sub(listing),
    }
    return composite_score(signals, profile=profile)
