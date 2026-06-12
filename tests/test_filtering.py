import unittest

from realestate_alert.filtering import matches_listing
from realestate_alert.models import Listing, SearchCriteria


class FilteringTests(unittest.TestCase):
    def test_matches_listing_inside_price_area_and_keyword_limits(self):
        criteria = SearchCriteria(
            locations=["강남구"],
            max_deposit=100000000,
            max_monthly_rent=5000000,
            min_area_m2=80,
            required_keywords=["병원", "의원"],
        )
        listing = Listing(
            source="sample",
            external_id="1",
            title="강남구 병원 가능 상가",
            location="서울 강남구 역삼동",
            deposit=80000000,
            monthly_rent=4500000,
            area_m2=95,
            floor="2층",
            premium=0,
            url="https://example.test/listings/1",
        )

        self.assertTrue(matches_listing(criteria, listing))

    def test_rejects_listing_over_budget(self):
        criteria = SearchCriteria(max_deposit=100000000, max_monthly_rent=5000000)
        listing = Listing(
            source="sample",
            external_id="2",
            title="예산 초과 상가",
            location="서울 강남구",
            deposit=120000000,
            monthly_rent=4500000,
            area_m2=90,
            floor="1층",
            premium=None,
            url="https://example.test/listings/2",
        )

        self.assertFalse(matches_listing(criteria, listing))

    def test_rejects_listing_without_required_keyword(self):
        criteria = SearchCriteria(required_keywords=["병원"])
        listing = Listing(
            source="sample",
            external_id="3",
            title="일반 사무실",
            location="서울 강남구",
            deposit=50000000,
            monthly_rent=3000000,
            area_m2=70,
            floor="5층",
            premium=None,
            url="https://example.test/listings/3",
        )

        self.assertFalse(matches_listing(criteria, listing))
