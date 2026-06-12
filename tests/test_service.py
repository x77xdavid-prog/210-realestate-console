import json
import tempfile
import unittest
from pathlib import Path

from realestate_alert.config import load_config
from realestate_alert.service import run_once


class ServiceTests(unittest.TestCase):
    def test_run_once_notifies_only_matching_new_listings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            listings_path = root / "listings.json"
            db_path = root / "seen.sqlite3"
            config_path = root / "config.json"
            listings_path.write_text(
                json.dumps(
                    [
                        {
                            "source": "manual",
                            "external_id": "match",
                            "title": "강남 병원 가능 상가",
                            "location": "서울 강남구",
                            "deposit": 80000000,
                            "monthly_rent": 4000000,
                            "area_m2": 90,
                            "floor": "2층",
                            "premium": 0,
                            "url": "https://example.test/match",
                        },
                        {
                            "source": "manual",
                            "external_id": "miss",
                            "title": "예산 초과 상가",
                            "location": "서울 강남구",
                            "deposit": 200000000,
                            "monthly_rent": 4000000,
                            "area_m2": 90,
                            "floor": "2층",
                            "premium": 0,
                            "url": "https://example.test/miss",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config_path.write_text(
                json.dumps(
                    {
                        "database_path": str(db_path),
                        "criteria": {
                            "locations": ["강남구"],
                            "max_deposit": 100000000,
                            "max_monthly_rent": 5000000,
                            "min_area_m2": 80,
                            "required_keywords": ["병원"],
                        },
                        "sources": [{"type": "json_file", "path": str(listings_path)}],
                        "notifiers": [{"type": "memory"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = load_config(config_path)

            first_result = run_once(config)
            second_result = run_once(config)

        self.assertEqual([listing.external_id for listing in first_result.notified], ["match"])
        self.assertEqual(second_result.notified, [])
