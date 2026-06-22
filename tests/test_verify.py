import json
import unittest
from unittest import mock

from realestate_alert.building_ledger import BuildingTitle
from realestate_alert.land_info import LandSummary
from realestate_alert.models import Listing
from realestate_alert.verify import (
    _resolve_market_region,
    enrich_listing,
    market_for_address,
    resolve_parcel,
    verify_address,
)

from tests.test_building_ledger import TITLE_XML
from tests.test_land_info import _route_fetcher as land_fetcher
from tests.test_market_price import TRADES_XML


def _combined_fetcher(url: str) -> str:
    if "BldRgstHubService" in url:
        return TITLE_XML
    if "RTMSDataSvcNrgTrade" in url:
        return TRADES_XML
    return land_fetcher(url)


class VerifyAddressTests(unittest.TestCase):
    def test_full_report_with_all_sources(self):
        env = {"DATA_GO_KR_API_KEY": "k1", "VWORLD_API_KEY": "k2"}
        with mock.patch.dict("os.environ", env, clear=False):
            report = verify_address("서울 양천구 목동 917-9", market_months=1, fetcher=_combined_fetcher)

        self.assertEqual(report["parcel"]["pnu"], "1147010100109170009")
        self.assertEqual(report["building"]["parking_spaces"], 4)
        self.assertEqual(report["building"]["approval_year"], 2008)
        self.assertEqual(report["land"]["zoning_names"], ["제2종일반주거지역"])
        self.assertEqual(report["land"]["official_price_per_m2"], 6120000)
        self.assertEqual(report["market"]["trade_count"], 1)
        self.assertEqual(report["errors"], {})

    def test_missing_keys_reported_per_source(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            report = verify_address("서울 양천구 목동 917-9", market_months=1, fetcher=_combined_fetcher)

        self.assertIsNone(report["building"])
        self.assertIsNone(report["land"])
        self.assertIsNone(report["market"])
        self.assertIn("DATA_GO_KR_API_KEY", report["errors"]["building"])
        self.assertIn("VWORLD_API_KEY", report["errors"]["land"])

    def test_unparseable_address_short_circuits(self):
        report = verify_address("이상한 주소", fetcher=_combined_fetcher)
        self.assertIn("address", report["errors"])
        self.assertIsNone(report["parcel"])


class MarketForAddressTests(unittest.TestCase):
    """경량 시세 전용 헬퍼 — verify의 3중 호출 없이 실거래만 조회한다."""

    def test_returns_market_summary_only(self):
        env = {"DATA_GO_KR_API_KEY": "k1"}
        with mock.patch.dict("os.environ", env, clear=False):
            result = market_for_address(
                "서울 양천구 목동 917-9", market_months=1, fetcher=_combined_fetcher
            )
        self.assertIsNotNone(result["market"])
        self.assertEqual(result["market"]["trade_count"], 1)
        self.assertIn("recent_trades", result["market"])
        self.assertIsNone(result["error"])

    def test_missing_key_reports_error_and_absorbs(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            result = market_for_address(
                "서울 양천구 목동 917-9", market_months=1, fetcher=_combined_fetcher
            )
        self.assertIsNone(result["market"])
        self.assertIn("DATA_GO_KR_API_KEY", result["error"])

    def test_unparseable_address_returns_error(self):
        result = market_for_address("이상한 주소", fetcher=_combined_fetcher)
        self.assertIsNone(result["market"])
        self.assertIsNotNone(result["error"])


def _vworld_code_fetcher(level4lc):
    def fetch(url):
        return json.dumps({"response": {"status": "OK",
                          "refined": {"structure": {"level4LC": level4lc}}}})
    return fetch


class ResolveMarketRegionTests(unittest.TestCase):
    """시군구 lawd_cd 해석 — 하드코딩 테이블 우선, 그 외 전국은 VWorld 보강."""

    def setUp(self):
        import realestate_alert.land_info as land_info
        land_info._district_cache.clear()

    def test_uses_table_without_external_call(self):
        def boom(url):
            raise AssertionError("테이블에 있으면 VWorld를 호출하면 안 된다")

        lawd, dong = _resolve_market_region("서울 양천구 목동 917-9", boom)
        self.assertEqual(lawd, "11470")
        self.assertEqual(dong, "목동")

    def test_falls_back_to_vworld_for_other_regions(self):
        with mock.patch.dict("os.environ", {"VWORLD_API_KEY": "k"}, clear=False):
            lawd, dong = _resolve_market_region(
                "서울특별시 성북구 정릉동 508-123",
                _vworld_code_fetcher("1129013300105080123"),
            )
        self.assertEqual(lawd, "11290")  # level4LC 앞 5자리
        self.assertEqual(dong, "정릉동")

    def test_returns_none_when_unresolvable(self):
        with mock.patch.dict("os.environ", {"VWORLD_API_KEY": "k"}, clear=False):
            lawd, _ = _resolve_market_region("부산 해운대구 우동 1", lambda url: "{}")
        self.assertIsNone(lawd)


class ResolveParcelTests(unittest.TestCase):
    """전국 ParcelAddress 해석 — 테이블 우선, 없으면 VWorld level4LC 분해."""

    def setUp(self):
        import realestate_alert.land_info as land_info
        land_info._district_cache.clear()

    def test_table_first_no_external(self):
        def boom(url):
            raise AssertionError("테이블에 있으면 VWorld를 호출하면 안 된다")

        parcel = resolve_parcel("서울 양천구 목동 917-9", boom)
        self.assertEqual(parcel.sigungu_code, "11470")
        self.assertEqual(parcel.pnu, "1147010100109170009")

    def test_vworld_decomposes_full_code(self):
        fetch = _vworld_code_fetcher("1129013300105080123")
        # level2/level3도 함께
        def fetch_named(url):
            return json.dumps({"response": {"refined": {"structure": {
                "level4LC": "1129013300105080123", "level2": "성북구", "level3": "정릉동"}}}})

        with mock.patch.dict("os.environ", {"VWORLD_API_KEY": "k"}, clear=False):
            parcel = resolve_parcel("서울특별시 성북구 정릉동 508-123", fetch_named)
        self.assertEqual(parcel.sigungu_code, "11290")
        self.assertEqual(parcel.bjdong_code, "13300")
        self.assertEqual(parcel.bun, 508)
        self.assertEqual(parcel.ji, 123)
        self.assertFalse(parcel.mountain)
        self.assertEqual(parcel.pnu, "1129013300105080123")
        self.assertEqual(parcel.dong, "정릉동")

    def test_short_code_returns_none(self):
        with mock.patch.dict("os.environ", {"VWORLD_API_KEY": "k"}, clear=False):
            parcel = resolve_parcel("서울특별시 성북구 정릉동", _vworld_code_fetcher("11290"))
        self.assertIsNone(parcel)


class EnrichListingTests(unittest.TestCase):
    def test_fills_only_missing_fields(self):
        listing = Listing(
            source="manual",
            external_id="yc-010",
            title="목동 검증 대상",
            location="서울 양천구 목동 917-9",
            deposit=0,
            monthly_rent=0,
            area_m2=118,
            floor="2층",
            premium=0,
            url="https://example.test/yc-010",
            parking_spaces=10,
        )
        building = BuildingTitle(
            building_name="목동메디컬빌딩",
            main_purpose="제2종근린생활시설",
            plat_area_m2=242.5,
            arch_area_m2=140.2,
            total_area_m2=386.4,
            building_coverage_ratio=52.3,
            floor_area_ratio=183.1,
            ground_floors=5,
            underground_floors=1,
            parking_spaces=4,
            elevator_count=1,
            approval_date="20080417",
        )
        land = LandSummary(
            zoning_names=["제2종일반주거지역"],
            road_side="중로한면",
            road_width_hint_m=12.0,
        )

        enriched = enrich_listing(listing, building, land)

        self.assertEqual(enriched.parking_spaces, 10)  # 기존 값 보존
        self.assertEqual(enriched.land_area_m2, 242.5)
        self.assertEqual(enriched.floors_total, 5)
        self.assertEqual(enriched.approval_year, 2008)
        self.assertTrue(enriched.elevator)
        self.assertEqual(enriched.zoning, "제2종일반주거지역")
        self.assertIn("중로한면", enriched.road_access)

    def test_no_sources_returns_same_listing(self):
        listing = Listing(
            source="manual",
            external_id="yc-011",
            title="변경 없음",
            location="서울 양천구 목동 1-1",
            deposit=0,
            monthly_rent=0,
            area_m2=100,
            floor="1층",
            premium=0,
            url="https://example.test/yc-011",
        )
        self.assertIs(enrich_listing(listing, None, None), listing)
