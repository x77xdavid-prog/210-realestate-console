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
