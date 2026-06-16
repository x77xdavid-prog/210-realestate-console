import json
import unittest
from unittest import mock

from realestate_alert.onbid import OnbidSource, _first_int


class FirstIntTests(unittest.TestCase):
    def test_extracts_first_comma_number(self):
        self.assertEqual(_first_int("최저 1,000,000원"), 1000000)
        self.assertEqual(_first_int("100,000,000"), 100000000)

    def test_returns_none_when_no_number(self):
        self.assertIsNone(_first_int(""))
        self.assertIsNone(_first_int("-"))
        self.assertIsNone(_first_int(None))

ONBID_JSON = json.dumps(
    {
        "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
        "body": {
            "totalCount": 2,
            "items": {
                "item": [
                    {
                        "cltrMngNo": "2026-0123-000456",
                        "onbidCltrNm": "서울특별시 양천구 신정동 321-6 근린생활시설",
                        "lctnSdnm": "서울특별시",
                        "lctnSggnm": "양천구",
                        "lctnEmdNm": "신정동",
                        "cltrUsgMclsCtgrNm": "근린생활시설",
                        "apslEvlAmt": "1850000000",
                        "lowstBidPrcIndctCont": "1,480,000,000원",
                        "cltrBidBgngDt": "202606150900",
                        "cltrBidEndDt": "202606171700",
                        "pbctStatNm": "입찰진행중",
                        "usbdNft": "1",
                        "landSqms": "250.5",
                        "bldSqms": "480.2",
                    },
                    {
                        "cltrMngNo": "2026-0123-000789",
                        "onbidCltrNm": "양천구 목동 나대지",
                        "lctnSdnm": "서울특별시",
                        "lctnSggnm": "양천구",
                        "lctnEmdNm": "목동",
                        "cltrUsgLclsCtgrNm": "토지",
                        "apslEvlAmt": "920000000",
                        "pbctStatNm": "입찰준비중",
                        "landSqms": "310.0",
                        "bldSqms": "",
                    },
                ]
            },
        },
    },
    ensure_ascii=False,
)


class OnbidSourceTests(unittest.TestCase):
    def test_fetch_maps_items_to_listings(self):
        captured = {}

        def fake_fetch(url):
            captured["url"] = url
            return ONBID_JSON

        source = OnbidSource(service_key="test-key", fetcher=fake_fetch)
        listings = source.fetch()

        self.assertIn("lctnSggnm=%EC%96%91%EC%B2%9C%EA%B5%AC", captured["url"])
        self.assertIn("resultType=json", captured["url"])
        self.assertEqual(len(listings), 2)

        building = listings[0]
        self.assertEqual(building.source, "onbid")
        self.assertEqual(building.external_id, "2026-0123-000456")
        self.assertIn("[공매]", building.title)
        self.assertIn("근린생활시설", building.title)
        # 물건명에 지번이 있으면 필지 단위 주소를 사용한다 (네이버 부동산 연동 정확도)
        self.assertEqual(building.location, "서울특별시 양천구 신정동 321-6")
        self.assertEqual(building.property_type, "building")
        self.assertEqual(building.area_m2, 480.2)
        self.assertIn("감정가 1,850,000,000원", building.buildable_note)
        self.assertIn("최저입찰 1,480,000,000원", building.buildable_note)
        self.assertIn("입찰진행중", building.buildable_note)

        land = listings[1]
        self.assertEqual(land.property_type, "land")
        self.assertEqual(land.area_m2, 310.0)
        # 물건명에 지번이 없으면 시도/시군구/읍면동 조합을 사용한다
        self.assertEqual(land.location, "서울특별시 양천구 목동")

    def test_fetch_without_key_returns_empty(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            source = OnbidSource(fetcher=lambda url: ONBID_JSON)
            self.assertEqual(source.fetch(), [])

    def test_fetch_handles_single_item_dict(self):
        payload = json.dumps(
            {
                "body": {
                    "items": {
                        "item": {
                            "cltrMngNo": "2026-1",
                            "onbidCltrNm": "단일 물건",
                            "lctnSdnm": "서울특별시",
                            "lctnSggnm": "양천구",
                            "bldSqms": "100",
                        }
                    }
                }
            },
            ensure_ascii=False,
        )
        source = OnbidSource(service_key="k", fetcher=lambda url: payload)
        listings = source.fetch()
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].external_id, "2026-1")

    def test_fetch_handles_malformed_response(self):
        source = OnbidSource(service_key="k", fetcher=lambda url: "not-json")
        self.assertEqual(source.fetch(), [])

    def test_fetch_deduplicates_by_management_number(self):
        payload = json.dumps(
            {
                "body": {
                    "items": {
                        "item": [
                            {"cltrMngNo": "2026-1", "onbidCltrNm": "회차1", "lctnSdnm": "서울특별시", "bldSqms": "100"},
                            {"cltrMngNo": "2026-1", "onbidCltrNm": "회차2", "lctnSdnm": "서울특별시", "bldSqms": "100"},
                            {"cltrMngNo": "2026-2", "onbidCltrNm": "다른 물건", "lctnSdnm": "서울특별시", "bldSqms": "50"},
                        ]
                    }
                }
            },
            ensure_ascii=False,
        )
        source = OnbidSource(service_key="k", fetcher=lambda url: payload)
        listings = source.fetch()
        self.assertEqual([listing.external_id for listing in listings], ["2026-1", "2026-2"])
