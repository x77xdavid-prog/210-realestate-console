import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from realestate_alert.models import Listing
from realestate_alert.store import LEDGER_STATUSES, ListingStore


def _sample_listing() -> Listing:
    return Listing(
        source="sample",
        external_id="same-id",
        title="신규 매물",
        location="서울 강남구",
        deposit=100000000,
        monthly_rent=4000000,
        area_m2=100,
        floor="1층",
        premium=0,
        url="https://example.test/listings/same-id",
    )


class StoreTests(unittest.TestCase):
    def test_records_new_listing_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            store.initialize()
            listing = _sample_listing()

            self.assertTrue(store.mark_seen_if_new(listing))
            self.assertFalse(store.mark_seen_if_new(listing))

    def test_is_recent_treats_unseen_and_recent_as_new(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            now = datetime(2026, 6, 11, 12, 0, 0, tzinfo=timezone.utc)

            self.assertTrue(store.is_recent(None, now=now))
            recent = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            self.assertTrue(store.is_recent(recent, now=now))
            old = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
            self.assertFalse(store.is_recent(old, now=now))

    def test_toggle_favorite_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            listing = {"title": "관심 매물", "location": "서울 양천구"}

            self.assertTrue(store.toggle_favorite("manual:yc-001", listing))
            self.assertEqual(store.favorite_identities(), {"manual:yc-001"})
            favorites = store.list_favorites()
            self.assertEqual(len(favorites), 1)
            self.assertEqual(favorites[0]["listing"]["title"], "관심 매물")

            self.assertFalse(store.toggle_favorite("manual:yc-001", listing))
            self.assertEqual(store.favorite_identities(), set())

    def test_ledger_upsert_list_delete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            listing = {"title": "매물장 매물", "location": "서울 양천구 목동"}

            store.upsert_ledger_entry("manual:yc-001", listing, LEDGER_STATUSES[0], "첫 메모")
            store.upsert_ledger_entry("manual:yc-001", listing, LEDGER_STATUSES[2], "방문 일정 협의")

            entries = store.list_ledger_entries()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["status"], LEDGER_STATUSES[2])
            self.assertEqual(entries[0]["memo"], "방문 일정 협의")

            self.assertTrue(store.delete_ledger_entry("manual:yc-001"))
            self.assertFalse(store.delete_ledger_entry("manual:yc-001"))
            self.assertEqual(store.list_ledger_entries(), [])

    def test_ledger_rejects_unknown_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            with self.assertRaises(ValueError):
                store.upsert_ledger_entry("manual:yc-001", {}, "없는상태", "")


class ChecklistReviewStoreTests(unittest.TestCase):
    def test_save_get_roundtrip_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            review = {
                "profile": "rebuild",
                "auto": {},
                "manual": {"loc_overall": {"status": "pass", "memo": ""}},
            }
            store.save_checklist_review("manual:yc-001", review)
            self.assertEqual(store.get_checklist_review("manual:yc-001")["profile"], "rebuild")

            store.save_checklist_review("manual:yc-001", {**review, "profile": "building"})
            self.assertEqual(store.get_checklist_review("manual:yc-001")["profile"], "building")
            self.assertIsNone(store.get_checklist_review("manual:none"))

    def test_all_checklist_reviews(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            store.save_checklist_review("a:1", {"profile": "building", "auto": {}, "manual": {}})
            store.save_checklist_review("b:2", {"profile": "land", "auto": {}, "manual": {}})
            self.assertEqual(set(store.all_checklist_reviews()), {"a:1", "b:2"})

    def test_delete_checklist_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            store.save_checklist_review("a:1", {"profile": "building", "auto": {}, "manual": {}})
            self.assertTrue(store.delete_checklist_review("a:1"))
            self.assertFalse(store.delete_checklist_review("a:1"))

    def test_ledger_delete_cascades_to_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            store.upsert_ledger_entry("a:1", {"title": "x"})
            store.save_checklist_review("a:1", {"profile": "building", "auto": {}, "manual": {}})
            store.delete_ledger_entry("a:1")
            self.assertIsNone(store.get_checklist_review("a:1"))

    def test_upsert_and_get_detail(self):
        import tempfile
        from pathlib import Path
        from realestate_alert.store import ListingStore
        with tempfile.TemporaryDirectory() as tmp:
            store = ListingStore(Path(tmp) / "t.db")
            store.initialize()
            store.upsert_detail("court:x-1", {"appraisal": 1, "photos": ["a"]})
            store.upsert_detail("court:x-1", {"appraisal": 2, "photos": ["a", "b"]})  # 덮어쓰기
            got = store.get_detail("court:x-1")
            self.assertEqual(got["appraisal"], 2)
            self.assertIsNone(store.get_detail("court:none"))
