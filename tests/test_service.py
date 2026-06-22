import json
import tempfile
import unittest
from pathlib import Path

from realestate_alert.config import load_config
from realestate_alert.models import Listing
from realestate_alert.service import collect_listings, run_once, enrich_candidates, is_court_hospital_candidate
from realestate_alert.store import ListingStore


def _make_listing(**kwargs) -> Listing:
    defaults = dict(
        source="court", external_id="t001", title="근린생활시설",
        location="서울 양천구", deposit=0, monthly_rent=0, area_m2=80.0,
        floor="2층", premium=None, url="https://example.test/t001",
        usage="근린생활시설", cs_no="2024타경58264",
        cort_ofc_cd="B000103", gds_seq="1",
    )
    defaults.update(kwargs)
    return Listing(**defaults)


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


class IsCourtHospitalCandidateTests(unittest.TestCase):
    def test_court_with_cs_no_and_commercial_usage_returns_true(self):
        ls = _make_listing(source="court", usage="근린생활시설", cs_no="2024타경58264")
        self.assertTrue(is_court_hospital_candidate(ls))

    def test_court_sangga_usage_returns_true(self):
        ls = _make_listing(source="court", usage="상가", cs_no="2024타경00001")
        self.assertTrue(is_court_hospital_candidate(ls))

    def test_court_eommu_usage_returns_true(self):
        ls = _make_listing(source="court", usage="업무시설", cs_no="2024타경00002")
        self.assertTrue(is_court_hospital_candidate(ls))

    def test_onbid_returns_false(self):
        ls = _make_listing(source="onbid", usage="근린생활시설", cs_no="2024타경58264")
        self.assertFalse(is_court_hospital_candidate(ls))

    def test_court_apartment_returns_false(self):
        ls = _make_listing(source="court", usage="아파트", title="아파트 2층", cs_no="2024타경00003")
        self.assertFalse(is_court_hospital_candidate(ls))

    def test_court_without_cs_no_returns_false(self):
        ls = _make_listing(source="court", usage="근린생활시설", cs_no=None)
        self.assertFalse(is_court_hospital_candidate(ls))


class EnrichCandidatesTests(unittest.TestCase):
    def _make_store(self, tmp_dir: str) -> ListingStore:
        db_path = Path(tmp_dir) / "test.sqlite3"
        store = ListingStore(db_path)
        store.initialize()
        return store

    def test_fetcher_called_once_for_fresh_court_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            photo_dir = Path(tmp) / "photos"
            photo_dir.mkdir()
            call_count = {"n": 0}

            def fake_fetcher(params):
                call_count["n"] += 1
                return json.dumps({"data": {"dma_result": {"csPicLst": []}}})

            ls = _make_listing()
            count = enrich_candidates(
                [ls], store, photo_dir,
                is_candidate=lambda l: l.source == "court",
                fetcher=fake_fetcher,
            )
            self.assertEqual(call_count["n"], 1)
            self.assertEqual(count, 1)

    def test_fetcher_not_called_for_non_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            photo_dir = Path(tmp) / "photos"
            photo_dir.mkdir()
            call_count = {"n": 0}

            def fake_fetcher(params):
                call_count["n"] += 1
                return json.dumps({"data": {"dma_result": {"csPicLst": []}}})

            ls = _make_listing(source="onbid")
            count = enrich_candidates(
                [ls], store, photo_dir,
                is_candidate=lambda l: l.source == "court",
                fetcher=fake_fetcher,
            )
            self.assertEqual(call_count["n"], 0)
            self.assertEqual(count, 0)

    def test_fetcher_not_called_when_already_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            photo_dir = Path(tmp) / "photos"
            photo_dir.mkdir()
            ls = _make_listing()
            # Pre-populate cache
            store.upsert_detail(ls.identity, {"identity": ls.identity, "cached": True})
            call_count = {"n": 0}

            def fake_fetcher(params):
                call_count["n"] += 1
                return json.dumps({"data": {"dma_result": {"csPicLst": []}}})

            count = enrich_candidates(
                [ls], store, photo_dir,
                is_candidate=lambda l: l.source == "court",
                fetcher=fake_fetcher,
            )
            self.assertEqual(call_count["n"], 0)
            self.assertEqual(count, 0)

    def test_failure_is_absorbed_and_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = self._make_store(tmp)
            photo_dir = Path(tmp) / "photos"
            photo_dir.mkdir()

            def boom_fetcher(params):
                raise RuntimeError("network error")

            ls = _make_listing()
            # Should not raise, count = 0 (failed)
            count = enrich_candidates(
                [ls], store, photo_dir,
                is_candidate=lambda l: l.source == "court",
                fetcher=boom_fetcher,
            )
            self.assertEqual(count, 0)
