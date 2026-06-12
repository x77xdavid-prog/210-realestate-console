import unittest

from realestate_alert.models import Listing
from realestate_alert.registry import (
    RegistryStatus,
    build_registry_target,
    detect_registry_risks,
)


class RegistryTests(unittest.TestCase):
    def test_builds_registry_target_from_listing_address(self):
        listing = Listing(
            source="manual",
            external_id="R-1",
            title="강남 병원 가능 상가",
            location="서울 강남구 역삼동 123-4",
            deposit=80000000,
            monthly_rent=4000000,
            area_m2=90,
            floor="2층",
            premium=0,
            url="https://example.test/R-1",
        )

        target = build_registry_target(listing)

        self.assertEqual(target.external_id, "R-1")
        self.assertEqual(target.address, "서울 강남구 역삼동 123-4")
        self.assertEqual(target.status, RegistryStatus.NEEDS_CHECK)

    def test_detects_risky_registry_rights(self):
        result = detect_registry_risks("소유자 홍길동 근저당권 설정 압류 가압류 전세권")

        self.assertEqual(result.status, RegistryStatus.RISK_FOUND)
        self.assertEqual(result.owner_names, ["홍길동"])
        self.assertEqual(result.risk_keywords, ["근저당권", "압류", "가압류", "전세권"])

    def test_marks_registry_checked_when_no_risk_keyword(self):
        result = detect_registry_risks("소유자 김철수 특이사항 없음")

        self.assertEqual(result.status, RegistryStatus.CHECKED)
        self.assertEqual(result.owner_names, ["김철수"])
        self.assertEqual(result.risk_keywords, [])
