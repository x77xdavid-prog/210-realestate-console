import json
import tempfile
import unittest
from pathlib import Path

from realestate_alert.config import load_config
from realestate_alert.service import collect_listings, run_once


def _write_two_source_config(root: Path) -> Path:
    """json_file 소스 2개짜리 설정 — 진행 콜백이 소스 완료마다 호출되는지 검증용."""
    config_path = root / "config.json"
    paths = []
    for index in range(2):
        listings_path = root / f"src{index}.json"
        listings_path.write_text(
            json.dumps(
                [{
                    "source": "manual", "external_id": f"m{index}",
                    "title": "강남 병원 가능 상가", "location": "서울 강남구",
                    "deposit": 80000000, "monthly_rent": 4000000, "area_m2": 90,
                    "floor": "2층", "premium": 0, "url": f"https://example.test/{index}",
                }],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        paths.append(listings_path)
    config_path.write_text(
        json.dumps(
            {
                "database_path": str(root / "seen.sqlite3"),
                "criteria": {"locations": ["강남구"], "required_keywords": ["병원"]},
                "sources": [{"type": "json_file", "path": str(p)} for p in paths],
                "notifiers": [{"type": "memory"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return config_path


class CollectProgressTests(unittest.TestCase):
    def test_on_progress_called_once_per_source_with_rising_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(_write_two_source_config(Path(temp_dir)))
            updates: list[tuple[int, int, int]] = []
            snapshot = collect_listings(
                config,
                on_progress=lambda fetched, done, total: updates.append((len(fetched), done, total)),
            )

        self.assertEqual(snapshot.fetched_count, 2)
        # 소스 2개 → 콜백 2회, 완료 수는 1→2로 증가, 합계는 단조 증가
        self.assertEqual([u[1] for u in updates], [1, 2])
        self.assertTrue(all(u[2] == 2 for u in updates))
        self.assertEqual(updates[-1][0], 2)


class CollectDeadlineTests(unittest.TestCase):
    def test_deadline_drops_slow_source_and_returns_completed(self):
        """마감을 넘긴 느린 소스는 빼고, 끝난 소스 결과만으로 스냅샷을 만든다."""
        import threading
        import time as _time
        from unittest import mock
        from realestate_alert import service
        from realestate_alert.models import Listing

        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_config(_write_two_source_config(Path(temp_dir)))
            lock = threading.Lock()
            counter = {"n": 0}

            def fake_safe_fetch(source):
                with lock:
                    index = counter["n"]
                    counter["n"] += 1
                if index >= 1:  # 두 번째 소스만 느리게 (마감 초과)
                    _time.sleep(2)
                return [Listing(
                    source="manual", external_id=f"d{index}", title="병원 상가",
                    location="서울 강남구", deposit=0, monthly_rent=0, area_m2=0.0,
                    floor=None, premium=None, url=f"https://example.test/{index}",
                )]

            with mock.patch.object(service, "_safe_fetch", side_effect=fake_safe_fetch):
                snapshot = service.collect_listings(config, deadline_seconds=0.3)

        # 빠른 소스 1건만 들어오고, 느린 소스는 마감으로 제외된다
        self.assertEqual(snapshot.fetched_count, 1)


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
