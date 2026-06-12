"""병원건물 매입·신축 체크리스트 정의와 매물 검토(자동 판정 + 점수) 로직.

문서 근거: docs/병원건물_매입_신축_체크리스트.md
검토 프로필 3종:
- building: 기존 건물 사용 (매입)
- rebuild:  철거 후 신축 — 건물 물리조건 무관, 토지 용도·도로·입지 중심
- land:     나대지 신축
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

PROFILES: dict[str, str] = {
    "building": "기존 건물 사용 (매입)",
    "rebuild": "철거 후 신축",
    "land": "나대지 신축",
}

CATEGORY_ORDER: tuple[str, ...] = ("입지", "법규", "권리", "물리", "신축", "철거", "재무")

AUTO_STATUSES: tuple[str, ...] = ("pass", "warn", "fail", "unknown", "info")
MANUAL_STATUSES: tuple[str, ...] = ("pass", "fail", "na", "unchecked")


@dataclass(frozen=True)
class ChecklistItem:
    item_id: str
    category: str
    label: str
    description: str
    kind: str  # "auto" | "info" | "manual"
    profiles: tuple[str, ...]
    critical: bool = False
    weight: float = 1.0


_B = ("building",)
_R = ("rebuild",)
_BR = ("building", "rebuild")
_RL = ("rebuild", "land")
_ALL = ("building", "rebuild", "land")

CHECKLIST_ITEMS: tuple[ChecklistItem, ...] = (
    # --- 입지 ---
    ChecklistItem(
        "loc_overall", "입지", "입지 종합 판단",
        "배후 수요·접근성·가시성을 종합한 최종 입지 판단. 부적합이면 다른 조건과 무관하게 탈락.",
        "manual", _ALL, critical=True, weight=2.0,
    ),
    ChecklistItem(
        "loc_population", "입지", "배후 인구·고령 비율",
        "반경 1~3km 인구수와 50대 이상 비율 (정형외과 주 수요층).",
        "manual", _ALL,
    ),
    ChecklistItem(
        "loc_competition", "입지", "경쟁 의원 분석",
        "반경 1km 내 정형외과·재활의학과·통증의학과 수와 규모.",
        "manual", _ALL,
    ),
    ChecklistItem(
        "loc_transit", "입지", "대중교통 접근성",
        "버스정류장·지하철역 도보 5분 이내 여부.",
        "manual", _ALL,
    ),
    ChecklistItem(
        "loc_visibility", "입지", "가시성·간판 노출",
        "대로변·코너 여부, 간판 노출 면적, 차량 진입 동선.",
        "manual", _ALL,
    ),
    ChecklistItem(
        "loc_pharmacy", "입지", "약국 연계",
        "인근 약국 유무 또는 약국 유치 가능 공간.",
        "manual", _ALL, weight=0.5,
    ),
    # --- 법규 ---
    ChecklistItem(
        "zoning", "법규", "용도지역",
        "의원/병원 용도가 허용되는 용도지역인지. 전용주거지역은 제한이 큼.",
        "auto", _ALL, critical=True, weight=2.0,
    ),
    ChecklistItem(
        "current_use", "법규", "현재 건물 용도",
        "건축물대장 주용도 — 의원 용도(1종 근생) 여부, 용도변경 필요성 판단 기초.",
        "info", _B,
    ),
    ChecklistItem(
        "use_change", "법규", "용도변경 가능성",
        "의원 용도로 용도변경 가능 여부와 비용 — 주차 추가 확보 요구가 걸림돌이 되는 경우 많음.",
        "manual", _B,
    ),
    ChecklistItem(
        "parking", "법규", "법정 주차대수",
        "대장 주차대수가 연면적 기준 추정 법정대수(150㎡당 1대) 이상인지. 지자체 조례 확인 필요.",
        "auto", _B, weight=1.5,
    ),
    ChecklistItem(
        "elevator", "법규", "승강기",
        "2층 이상 개원 시 사실상 필수 — 침대·휠체어 규격 여부는 현장 확인.",
        "auto", _B,
    ),
    ChecklistItem(
        "disabled_access", "법규", "장애인 편의시설",
        "바닥면적 100㎡ 이상 의원은 경사로·장애인화장실 등 의무 — 설치 가능 여부.",
        "manual", _B,
    ),
    ChecklistItem(
        "fire_safety", "법규", "소방·피난",
        "스프링클러·피난계단·방화구획 — 노후 건물 보강 비용 확인.",
        "manual", _B,
    ),
    ChecklistItem(
        "violation_check", "법규", "위반건축물 여부",
        "건축물대장(세움터) 위반건축물 표시 확인 — API 미제공으로 직접 확인 필요.",
        "manual", _B, critical=True,
    ),
    # --- 권리 ---
    ChecklistItem(
        "registry_rights", "권리", "등기부 권리관계",
        "근저당·가압류·가처분 등, 채권최고액이 매매가 대비 과도하지 않은지.",
        "manual", _BR,
    ),
    ChecklistItem(
        "tenant_eviction", "권리", "임차인 명도",
        "기존 임차인 명도 일정·비용. 철거 전제면 전원 명도 필수 — 실패 시 사업 전체가 막힘.",
        "manual", _BR, critical=True, weight=1.5,
    ),
    ChecklistItem(
        "vat_clause", "권리", "부가세 특약",
        "의료업은 면세사업이라 건물분 부가세 환급 불가 — 계약서에 부가세 별도/포함 명시.",
        "manual", _BR,
    ),
    # --- 물리 (기존 건물 사용 시에만) ---
    ChecklistItem(
        "ceiling_height", "물리", "층고",
        "유효 천장고 2.7m 이상 (천장 매립 장비·덕트 감안).",
        "manual", _B,
    ),
    ChecklistItem(
        "mri_load", "물리", "MRI 하중·반입",
        "본체 3~5톤 — 구조 보강 필요 여부, 반입 경로(크레인·벽체 개구). 장비업체 현장 실사.",
        "manual", _B, weight=1.5,
    ),
    ChecklistItem(
        "radiation_shield", "물리", "방사선 차폐",
        "X-ray·C-arm실 납 차폐 시공 가능 여부 — 설치 신고·검사 통과 필요.",
        "manual", _B,
    ),
    ChecklistItem(
        "power_capacity", "물리", "전기 용량",
        "MRI/CT 도입 시 수전용량 증설(별도 변압기) 가능 여부.",
        "manual", _B,
    ),
    ChecklistItem(
        "column_span", "물리", "기둥 간격",
        "물리치료실·운동치료실용 넓은 무주 공간 확보 가능 여부.",
        "manual", _B, weight=0.5,
    ),
    ChecklistItem(
        "building_age", "물리", "건물 노후도",
        "준공 30년 이상이면 보강·리모델링 비용 변수.",
        "auto", _B, weight=0.5,
    ),
    # --- 신축 (철거 후 신축·나대지) ---
    ChecklistItem(
        "road_access", "신축", "도로 접면",
        "폭 4m 이상 도로 접면 — 맹지면 건축 불가로 즉시 탈락.",
        "auto", _RL, critical=True, weight=2.0,
    ),
    ChecklistItem(
        "buildable_volume", "신축", "신축 가능 볼륨",
        "대지면적 × 용적률 = 최대 연면적이 목표 규모를 충족하는지 (법정 한도는 조례 확인).",
        "info", _RL,
    ),
    ChecklistItem(
        "land_price_basis", "신축", "토지 가치 기준 가격",
        "건물값 0으로 보고 공시지가·주변 토지 시세 대비 매물가 평가.",
        "info", _RL,
    ),
    ChecklistItem(
        "sunlight_limit", "신축", "일조권·형태 제한",
        "일조권 사선제한·고도지구·지구단위계획 등 형태 제한.",
        "manual", _RL,
    ),
    ChecklistItem(
        "ground_condition", "신축", "지반 조건",
        "연약지반·암반 여부 (파일·발파 비용), 인접 건물 영향.",
        "manual", _RL, weight=0.5,
    ),
    ChecklistItem(
        "utilities", "신축", "기반시설 인입",
        "상수·하수·전기·도시가스 인입 여부와 비용.",
        "manual", _RL, weight=0.5,
    ),
    ChecklistItem(
        "parking_layout", "신축", "주차 확보 대지 형상",
        "법정 주차대수를 충족할 수 있는 대지 형상인지 (지하주차장 필요 시 공사비 급증).",
        "manual", _RL,
    ),
    # --- 철거 (철거 후 신축만) ---
    ChecklistItem(
        "rebuild_age_ok", "철거", "기존 건물 상태",
        "철거 전제 — 건물 노후도 무관, 오히려 매입가 협상에 유리.",
        "auto", _R, weight=0.0,
    ),
    ChecklistItem(
        "demolition_cost", "철거", "철거비·석면 조사",
        "석면 사전조사(의무)·해체 허가·폐기물 처리비 견적.",
        "manual", _R,
    ),
    ChecklistItem(
        "demolition_schedule", "철거", "철거 일정",
        "멸실등기 → 착공까지 1~3개월이 전체 개원 일정에 반영됐는지.",
        "manual", _R, weight=0.5,
    ),
    ChecklistItem(
        "neighbor_complaints", "철거", "인접 민원 대비",
        "철거+신축 공사 소음·분진, 인접 건물 균열 분쟁 — 사전 안전진단.",
        "manual", _R, weight=0.5,
    ),
    # --- 재무 ---
    ChecklistItem(
        "price_market", "재무", "시세 대비 가격",
        "주변 ㎡당 실거래가 대비 매물가 적정성 (+20% 초과 시 경고).",
        "auto", _B,
    ),
    ChecklistItem(
        "budget_total", "재무", "총사업비 예산 내",
        "매입가(+철거·공사비) + 취득세 + 인테리어 + 장비 + 예비비 10%가 예산 상한 이내.",
        "manual", _ALL, weight=1.5,
    ),
    ChecklistItem(
        "loan_plan", "재무", "대출 계획",
        "담보대출 LTV·메디컬론 — 신축 계열은 공사 중 이자(브릿지) 포함.",
        "manual", _ALL,
    ),
)

ITEM_IDS: frozenset[str] = frozenset(item.item_id for item in CHECKLIST_ITEMS)


def items_for_profile(profile: str) -> list[ChecklistItem]:
    if profile not in PROFILES:
        raise ValueError(f"지원하지 않는 검토 프로필: {profile}")
    return [item for item in CHECKLIST_ITEMS if profile in item.profiles]


def definition_payload() -> dict[str, Any]:
    return {
        "profiles": PROFILES,
        "categories": list(CATEGORY_ORDER),
        "items": [asdict(item) for item in CHECKLIST_ITEMS],
    }


# ===== 자동 판정 =====

PARKING_AREA_PER_SPACE_M2 = 150.0  # 의료시설 부설주차장 단순 추정 기준 — 지자체 조례 확인 필요
OLD_BUILDING_AGE_YEARS = 30
PRICE_PREMIUM_WARN_RATIO = 1.2  # 주변 ㎡당 시세 대비 20% 초과 시 경고
MIN_FLOORS_NEEDING_ELEVATOR = 2


def evaluate_auto_items(
    listing: dict[str, Any],
    report: dict[str, Any],
    now_year: int | None = None,
) -> dict[str, dict[str, str]]:
    """verify_address 리포트와 매물 정보로 auto/info 항목을 판정한다 (API 호출 없는 순수 함수)."""
    building = report.get("building") or {}
    land = report.get("land") or {}
    market = report.get("market") or {}
    year = now_year if now_year is not None else datetime.now(timezone.utc).year
    return {
        "zoning": _judge_zoning(land, listing),
        "elevator": _judge_elevator(building, listing),
        "parking": _judge_parking(building, listing),
        "building_age": _judge_building_age(building, listing, year),
        "rebuild_age_ok": _judge_rebuild_age(building, listing),
        "road_access": _judge_road_access(land, listing),
        "price_market": _judge_price_market(market, building, listing),
        "current_use": _info_current_use(building),
        "buildable_volume": _info_buildable_volume(building, listing),
        "land_price_basis": _info_land_price(land, building, listing),
    }


def _result(status: str, evidence: str) -> dict[str, str]:
    return {"status": status, "evidence": evidence}


def _listing_price_won(listing: dict[str, Any]) -> float | None:
    """월세 없는 매물의 보증금(=매매가/최저입찰가)을 가격으로 본다."""
    monthly = listing.get("monthly_rent") or 0
    deposit = listing.get("deposit") or 0
    if monthly == 0 and deposit > 0:
        return float(deposit)
    return None


def _judge_zoning(land: dict[str, Any], listing: dict[str, Any]) -> dict[str, str]:
    names = land.get("zoning_names") or []
    if not names and listing.get("zoning"):
        names = [str(listing["zoning"])]
    if not names:
        return _result("unknown", "용도지역 정보 없음 — 토지이용계획 확인 필요")
    joined = ", ".join(str(name) for name in names if name)
    if any("전용주거" in str(name) for name in names):
        return _result("warn", f"{joined} — 전용주거지역은 의원/병원 용도 제한이 큼 (조례 확인 필요)")
    return _result("pass", joined)


def _judge_elevator(building: dict[str, Any], listing: dict[str, Any]) -> dict[str, str]:
    count = building.get("elevator_count")
    has = (count > 0) if isinstance(count, (int, float)) else listing.get("elevator")
    floors = building.get("ground_floors") or listing.get("floors_total")
    if has is None:
        return _result("unknown", "승강기 정보 없음 — 건축물대장 확인 필요")
    if has:
        label = f"승강기 {int(count)}대" if isinstance(count, (int, float)) else "승강기 있음"
        return _result("pass", f"{label} — 침대·휠체어 규격 여부는 현장 확인")
    if isinstance(floors, (int, float)) and floors >= MIN_FLOORS_NEEDING_ELEVATOR:
        return _result("fail", f"지상 {int(floors)}층인데 승강기 없음 — 거동불편 환자 접근 불가")
    return _result("warn", "승강기 없음 — 1층 단독 사용이 아니면 설치 필요")


def _judge_parking(building: dict[str, Any], listing: dict[str, Any]) -> dict[str, str]:
    spaces = building.get("parking_spaces")
    if spaces is None:
        spaces = listing.get("parking_spaces")
    total_area = building.get("total_area_m2") or listing.get("building_area_m2")
    if spaces is None:
        return _result("unknown", "주차대수 정보 없음 — 건축물대장 확인 필요")
    if not total_area:
        return _result("unknown", f"주차 {int(spaces)}대 — 연면적 정보가 없어 법정대수 추정 불가")
    required = math.ceil(float(total_area) / PARKING_AREA_PER_SPACE_M2)
    detail = f"연면적 {float(total_area):,.0f}㎡ ÷ {PARKING_AREA_PER_SPACE_M2:.0f}㎡당 1대"
    if spaces >= required:
        return _result("pass", f"주차 {int(spaces)}대 ≥ 추정 법정 {required}대 ({detail})")
    return _result("warn", f"주차 {int(spaces)}대 < 추정 법정 {required}대 ({detail}) — 용도변경 시 추가 확보 요구 가능")


def _judge_building_age(building: dict[str, Any], listing: dict[str, Any], now_year: int) -> dict[str, str]:
    year = building.get("approval_year") or listing.get("approval_year")
    if not year:
        return _result("unknown", "준공년도 정보 없음")
    age = now_year - int(year)
    if age >= OLD_BUILDING_AGE_YEARS:
        return _result("warn", f"{year}년 준공 (약 {age}년 경과) — 구조 보강·리모델링 비용 변수")
    return _result("pass", f"{year}년 준공 (약 {age}년 경과)")


def _judge_rebuild_age(building: dict[str, Any], listing: dict[str, Any]) -> dict[str, str]:
    year = building.get("approval_year") or listing.get("approval_year")
    prefix = f"{year}년 준공 — " if year else ""
    return _result("pass", f"{prefix}철거 전제로 노후도 무관 (노후할수록 매입가 협상에 유리)")


def _judge_road_access(land: dict[str, Any], listing: dict[str, Any]) -> dict[str, str]:
    side = land.get("road_side") or listing.get("road_access")
    if not side:
        return _result("unknown", "도로 접면 정보 없음 — 토지이용계획 확인 필요")
    text = str(side)
    if "맹지" in text:
        return _result("fail", f"{text} — 도로 미접으로 건축 불가")
    width = land.get("road_width_hint_m")
    hint = f" (약 {width:g}m급)" if width else ""
    return _result("pass", f"{text}{hint}")


def _judge_price_market(
    market: dict[str, Any], building: dict[str, Any], listing: dict[str, Any]
) -> dict[str, str]:
    avg = market.get("avg_price_per_m2")
    if not avg:
        return _result("unknown", "주변 실거래 정보 없음 — 공공데이터 검증 필요")
    price = _listing_price_won(listing)
    area = building.get("total_area_m2") or listing.get("building_area_m2")
    if not price or not area:
        return _result("unknown", f"주변 ㎡당 평균 {_man(avg)} — 매물가/연면적 정보가 없어 자동 비교 불가")
    per = price / float(area)
    ratio = per / float(avg)
    summary = f"매물 ㎡당 {_man(per)} vs 주변 평균 {_man(avg)} ({ratio:.0%})"
    if ratio > PRICE_PREMIUM_WARN_RATIO:
        return _result("warn", f"{summary} — 시세 대비 고평가, 협상 여지 확인")
    return _result("pass", summary)


def _man(value: float) -> str:
    return f"{value / 10000:,.0f}만원"


def _info_current_use(building: dict[str, Any]) -> dict[str, str]:
    purpose = building.get("main_purpose")
    if not purpose:
        return _result("unknown", "건축물대장 주용도 정보 없음")
    return _result("info", f"현재 주용도: {purpose} — 의원(1종 근생) 해당 여부·용도변경 필요성 판단")


def _info_buildable_volume(building: dict[str, Any], listing: dict[str, Any]) -> dict[str, str]:
    land_area = building.get("plat_area_m2") or listing.get("land_area_m2")
    far = listing.get("floor_area_ratio") or building.get("floor_area_ratio")
    if not land_area:
        return _result("unknown", "대지면적 정보 없음")
    if not far:
        return _result("info", f"대지 {float(land_area):,.0f}㎡ — 용적률 정보가 없어 볼륨 계산 불가 (용도지역 한도 확인)")
    max_total = float(land_area) * float(far) / 100.0
    pyeong = max_total * 0.3025
    return _result(
        "info",
        f"대지 {float(land_area):,.0f}㎡ × 용적률 {float(far):g}% ≈ 연면적 {max_total:,.0f}㎡"
        f" ({pyeong:,.0f}평) — 법정 한도는 조례 확인",
    )


def _info_land_price(
    land: dict[str, Any], building: dict[str, Any], listing: dict[str, Any]
) -> dict[str, str]:
    price_per = land.get("official_price_per_m2")
    land_area = building.get("plat_area_m2") or listing.get("land_area_m2")
    if not price_per or not land_area:
        return _result("unknown", "공시지가 또는 대지면적 정보 없음")
    total = float(price_per) * float(land_area)
    year = land.get("official_price_year")
    base = f"공시지가 합계 약 {total / 100000000:,.1f}억원" + (f" ({year}년 기준)" if year else "")
    price = _listing_price_won(listing)
    if price:
        return _result("info", f"{base} — 매물가 {price / 100000000:,.1f}억원은 공시지가의 {price / total:.1f}배")
    return _result("info", base)


# ===== 점수·등급 =====

GRADE_THRESHOLDS: tuple[tuple[float, str], ...] = ((85.0, "A"), (70.0, "B"), (50.0, "C"))
NO_GO_GRADE = "부적합"

_STATUS_EARN_RATIO = {"pass": 1.0, "warn": 0.5, "fail": 0.0}


def compute_review(
    profile: str,
    auto_results: dict[str, dict[str, str]] | None,
    manual_results: dict[str, dict[str, str]] | None,
) -> dict[str, Any]:
    """저장된 자동/수동 판정을 항목 정의와 병합해 점수·등급·진행률을 계산한다."""
    items = items_for_profile(profile)
    auto_results = auto_results or {}
    manual_results = manual_results or {}

    rows: list[dict[str, Any]] = []
    earned = 0.0
    possible = 0.0
    no_go = False
    auto_done = auto_total = manual_done = manual_total = 0

    for item in items:
        auto_raw = auto_results.get(item.item_id) or {}
        manual_raw = manual_results.get(item.item_id) or {}
        evidence = str(auto_raw.get("evidence", ""))
        memo = str(manual_raw.get("memo", ""))

        if item.kind == "auto":
            status = auto_raw.get("status", "unknown")
            if status not in AUTO_STATUSES:
                status = "unknown"
            auto_total += 1
            if status != "unknown":
                auto_done += 1
        else:
            # info 항목도 최종 확정(점수 반영)은 수동 체크로 한다
            status = manual_raw.get("status", "unchecked")
            if status not in MANUAL_STATUSES:
                status = "unchecked"
            manual_total += 1
            if status != "unchecked":
                manual_done += 1

        if status in _STATUS_EARN_RATIO:
            earned += _STATUS_EARN_RATIO[status] * item.weight
            possible += item.weight
            if item.critical and status == "fail":
                no_go = True

        rows.append(
            {
                **asdict(item),
                "status": status,
                "evidence": evidence,
                "memo": memo,
            }
        )

    score: float | None = None
    grade: str | None = None
    if possible > 0:
        score = round(earned / possible * 100, 1)
        grade = "D"
        for threshold, letter in GRADE_THRESHOLDS:
            if score >= threshold:
                grade = letter
                break
    if no_go:
        grade = NO_GO_GRADE

    return {
        "profile": profile,
        "score": score,
        "grade": grade,
        "no_go": no_go,
        "progress": {
            "auto_done": auto_done,
            "auto_total": auto_total,
            "manual_done": manual_done,
            "manual_total": manual_total,
        },
        "items": rows,
    }
