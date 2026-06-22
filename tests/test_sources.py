import json
import tempfile
import unittest
from pathlib import Path

from realestate_alert.sources import JsonFileSource


class SourceTests(unittest.TestCase):
    def test_loads_listings_from_json_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "listings.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "source": "manual",
                            "external_id": "A-1",
                            "title": "강남 병원 가능",
                            "location": "서울 강남구",
                            "deposit": 90000000,
                            "monthly_rent": 4200000,
                            "area_m2": 88,
                            "floor": "3층",
                            "premium": 0,
                            "url": "https://example.test/A-1",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            listings = JsonFileSource(path).fetch()

        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0].external_id, "A-1")
        self.assertEqual(listings[0].title, "강남 병원 가능")

    def test_loads_auction_fields_with_comma_numbers(self):
        # 경매/공매 시드: 콤마가 든 금액 문자열도 안전하게 파싱하고 입찰일자를 읽는다.
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "listings.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "source": "onbid",
                            "external_id": "o-1",
                            "title": "[공매] 목동 근린상가",
                            "location": "서울 양천구 목동 1",
                            "deposit": 0,
                            "monthly_rent": 0,
                            "area_m2": 120,
                            "url": "https://www.onbid.co.kr",
                            "appraisal_price": "1,850,000,000",
                            "min_bid_price": "1,480,000,000",
                            "sale_date": "20260626",
                            "bid_begin": "20260620",
                            "bid_end": "20260626",
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            listing = JsonFileSource(path).fetch()[0]

        self.assertEqual(listing.source, "onbid")
        self.assertEqual(listing.appraisal_price, 1850000000)
        self.assertEqual(listing.min_bid_price, 1480000000)
        self.assertEqual(listing.sale_date, "20260626")
        self.assertEqual(listing.bid_begin, "20260620")
        self.assertEqual(listing.bid_end, "20260626")
