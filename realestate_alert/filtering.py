from __future__ import annotations

from realestate_alert.models import Listing, SearchCriteria

# 공매·경매·LH는 임대가 아니라 '매입 후보' 소스다. 보증금/월세/권리금 같은
# 임대 조건으로 거르면 매물이 통째로 사라지므로 위치·키워드로만 일치 판정한다.
CANDIDATE_SOURCES = frozenset({"onbid", "court", "lh"})


def matches_listing(criteria: SearchCriteria, listing: Listing) -> bool:
    is_candidate = listing.source in CANDIDATE_SOURCES

    if criteria.locations and not _location_matches(criteria.locations, listing, is_candidate):
        return False
    if criteria.required_keywords and not listing.contains_any(criteria.required_keywords):
        return False
    # 면적은 '값이 있는데' 미달일 때만 제외한다. 0/미상은 데이터 부족 → 확인 필요로 통과.
    if criteria.min_area_m2 is not None and listing.area_m2 and listing.area_m2 < criteria.min_area_m2:
        return False
    # 임대 조건 상한은 임대형 매물(직접 등록·네이버 등)에만 적용한다.
    if not is_candidate:
        if criteria.max_deposit is not None and listing.deposit > criteria.max_deposit:
            return False
        if criteria.max_monthly_rent is not None and listing.monthly_rent > criteria.max_monthly_rent:
            return False
        if criteria.max_premium is not None and (listing.premium or 0) > criteria.max_premium:
            return False
    return True


def _location_matches(locations: list[str], listing: Listing, is_candidate: bool) -> bool:
    text = listing.location.lower()
    if any(location.lower() in text for location in locations):
        return True
    # LH처럼 시·도 단위로만 오는 공고는 구 단위로 거를 수 없어 후보로 통과시킨다.
    if is_candidate and not _has_district(listing.location):
        return True
    return False


def _has_district(location: str) -> bool:
    return any(token in location for token in ("구", "군"))
