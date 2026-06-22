import json
import unittest
from datetime import date
from unittest import mock

from realestate_alert.cheongyak import (
    fetch_nearby_supply,
    nearby_supply_report,
)

SUPPLY_JSON = json.dumps({
    "currentCount": 3,
    "data": [
        {
            "HOUSE_NM": "샘플자이 더포레", "HSSPLY_ADRES": "서울특별시 양천구 신정동 1번지",
            "SUBSCRPT_AREA_CODE_NM": "서울", "TOT_SUPLY_HSHLDCO": "1,200",
            "MVN_PREARNGE_YM": "202812", "RCRIT_PBLANC_DE": "2026-06-01",
            "PBLANC_URL": "https://www.applyhome.co.kr/x", "HOUSE_SECD_NM": "민영",
        },
        {  # 과거 입주 → upcoming_only로 제외
            "HOUSE_NM": "과거단지", "HSSPLY_ADRES": "서울특별시 양천구 목동 2",
            "MVN_PREARNGE_YM": "202001", "TOT_SUPLY_HSHLDCO": "300",
            "RCRIT_PBLANC_DE": "2019-01-01",
        },
        {  # 더 이른 미래 입주 → 정렬상 먼저
            "HOUSE_NM": "이른입주", "HSSPLY_ADRES": "서울특별시 양천구 신월동 3",
            "MVN_PREARNGE_YM": "202709", "TOT_SUPLY_HSHLDCO": "500",
            "RCRIT_PBLANC_DE": "2026-05-01",
        },
    ],
})

TODAY = date(2026, 6, 22)


class FetchNearbySupplyTests(unittest.TestCase):
    def test_filters_future_and_sorts_by_movein(self):
        with mock.patch.dict("os.environ", {"DATA_GO_KR_API_KEY": "k1"}):
            notices = fetch_nearby_supply("양천구", fetcher=lambda url: SUPPLY_JSON, today=TODAY)
        names = [n.house_name for n in notices]
        self.assertEqual(names, ["이른입주", "샘플자이 더포레"])  # 과거단지 제외, 입주월 오름차순
        self.assertEqual(notices[1].total_households, 1200)
        self.assertEqual(notices[1].move_in_label, "2028.12")

    def test_region_keyword_in_request_url(self):
        captured = {}

        def fake(url):
            captured["url"] = url
            return SUPPLY_JSON

        with mock.patch.dict("os.environ", {"DATA_GO_KR_API_KEY": "k1"}):
            fetch_nearby_supply("강남구", fetcher=fake, today=TODAY)
        # cond[HSSPLY_ADRES::LIKE]=강남구 가 인코딩되어 들어간다
        self.assertIn("HSSPLY_ADRES", captured["url"])
        self.assertIn("%EA%B0%95%EB%82%A8%EA%B5%AC", captured["url"])  # urlencode('강남구')


class NearbySupplyReportTests(unittest.TestCase):
    def test_report_success(self):
        with mock.patch.dict("os.environ", {"DATA_GO_KR_API_KEY": "k1"}):
            r = nearby_supply_report("양천구", today=TODAY, fetcher=lambda url: SUPPLY_JSON)
        self.assertIsNone(r["error"])
        self.assertEqual(len(r["supplies"]), 2)
        self.assertEqual(r["supplies"][0]["house_name"], "이른입주")

    def test_missing_key_absorbed(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            r = nearby_supply_report("양천구", today=TODAY, fetcher=lambda url: SUPPLY_JSON)
        self.assertEqual(r["supplies"], [])
        self.assertIn("DATA_GO_KR_API_KEY", r["error"])

    def test_empty_region(self):
        r = nearby_supply_report("", today=TODAY)
        self.assertIsNotNone(r["error"])
        self.assertEqual(r["supplies"], [])

    def test_bad_json_absorbed(self):
        with mock.patch.dict("os.environ", {"DATA_GO_KR_API_KEY": "k1"}):
            r = nearby_supply_report("양천구", today=TODAY, fetcher=lambda url: "<html>err</html>")
        self.assertEqual(r["supplies"], [])
        self.assertIsNotNone(r["error"])


if __name__ == "__main__":
    unittest.main()
