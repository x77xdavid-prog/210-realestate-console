from __future__ import annotations

from realestate_alert.models import Listing, SearchCriteria


def matches_listing(criteria: SearchCriteria, listing: Listing) -> bool:
    if criteria.locations and not any(
        location.lower() in listing.location.lower() for location in criteria.locations
    ):
        return False
    if criteria.max_deposit is not None and listing.deposit > criteria.max_deposit:
        return False
    if criteria.max_monthly_rent is not None and listing.monthly_rent > criteria.max_monthly_rent:
        return False
    if criteria.min_area_m2 is not None and listing.area_m2 < criteria.min_area_m2:
        return False
    if criteria.max_premium is not None:
        premium = listing.premium or 0
        if premium > criteria.max_premium:
            return False
    if criteria.required_keywords and not listing.contains_any(criteria.required_keywords):
        return False
    return True
