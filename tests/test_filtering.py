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

    def test_unknown_area_does_not_exclude(self):
        """면적 정보가 없는(0) 매물은 '미달'이 아니라 '확인 필요'로 통과시킨다."""
        criteria = SearchCriteria(min_area_m2=70, required_keywords=["토지"])
        listing = Listing(
            source="court",
            external_id="4",
            title="[경매] 서울특별시 양천구 신정동 토지",
            location="서울특별시 양천구 신정동 100-1",
            deposit=900000000,  # 최저매각가 — 임대 보증금 아님
            monthly_rent=0,
            area_m2=0.0,  # 경매 소스는 면적이 비어 있음
            floor=None,
            premium=None,
            url="https://www.courtauction.go.kr",
        )

        self.assertTrue(matches_listing(criteria, listing))

    def test_candidate_source_ignores_rental_ceilings(self):
        """공매·경매·LH 후보는 매입 대상이라 임대 보증금/월세 상한으로 거르지 않는다."""
        criteria = SearchCriteria(
            locations=["양천구"],
            max_deposit=150000000,
            max_monthly_rent=6000000,
            required_keywords=["상가"],
        )
        listing = Listing(
            source="onbid",
            external_id="5",
            title="[공매] 서울특별시 양천구 목동 상가",
            location="서울특별시 양천구 목동 531",
            deposit=800000000,  # 감정가 수준 — 상한 초과
            monthly_rent=0,
            area_m2=120,
            floor=None,
            premium=None,
            url="https://www.onbid.co.kr",
        )

        self.assertTrue(matches_listing(criteria, listing))

    def test_region_only_candidate_passes_location_filter(self):
        """LH처럼 시·도 단위로만 오는 공고는 구 단위 위치 필터로 거를 수 없어 통과시킨다."""
        criteria = SearchCriteria(locations=["양천구"], required_keywords=["상가"])
        listing = Listing(
            source="lh",
            external_id="6",
            title="[LH 상가] 희망상가 모집공고",
            location="서울특별시",
            deposit=0,
            monthly_rent=0,
            area_m2=0.0,
            floor=None,
            premium=None,
            url="https://apply.lh.or.kr",
        )

        self.assertTrue(matches_listing(criteria, listing))

    def test_candidate_with_district_still_filtered_by_location(self):
        """구 정보가 있는 후보는 검색 지역과 다르면 제외한다(지역 단위 통과는 시·도 공고에만)."""
        criteria = SearchCriteria(locations=["양천구"], required_keywords=["상가"])
        listing = Listing(
            source="onbid",
            external_id="7",
            title="[공매] 서울특별시 강서구 상가",
            location="서울특별시 강서구 등촌동 717",
            deposit=0,
            monthly_rent=0,
            area_m2=0.0,
            floor=None,
            premium=None,
            url="https://www.onbid.co.kr",
        )

        self.assertFalse(matches_listing(criteria, listing))

    def test_known_area_below_minimum_still_excluded(self):
        """면적이 '있는데' 미달이면 기존대로 제외한다(후보 여부와 무관)."""
        criteria = SearchCriteria(min_area_m2=70, required_keywords=["상가"])
        listing = Listing(
            source="onbid",
            external_id="8",
            title="[공매] 서울특별시 양천구 소형 상가",
            location="서울특별시 양천구 목동 1",
            deposit=0,
            monthly_rent=0,
            area_m2=30,  # 면적이 있고 미달
            floor=None,
            premium=None,
            url="https://www.onbid.co.kr",
        )

        self.assertFalse(matches_listing(criteria, listing))
