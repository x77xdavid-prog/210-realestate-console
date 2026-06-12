import tempfile
import unittest
from pathlib import Path

from realestate_alert.documents import (
    MAX_DOCUMENT_BYTES,
    content_disposition_for,
    count_all_documents,
    delete_all_documents,
    delete_document,
    document_path,
    list_documents,
    safe_filename,
    safe_identity,
    save_document,
)


class SafeNameTests(unittest.TestCase):
    def test_identity_sanitized(self):
        self.assertEqual(safe_identity("onbid:2026-0600-1"), "onbid_2026-0600-1")
        with self.assertRaises(ValueError):
            safe_identity("..")

    def test_filename_keeps_korean_blocks_traversal(self):
        self.assertEqual(safe_filename("등기부등본.pdf"), "등기부등본.pdf")
        self.assertEqual(safe_filename("..\\..\\evil.exe"), "evil.exe")
        self.assertEqual(safe_filename("a/b/../c.pdf"), "c.pdf")
        with self.assertRaises(ValueError):
            safe_filename("..")
        with self.assertRaises(ValueError):
            safe_filename(".hidden")

    def test_content_disposition(self):
        mime, disposition = content_disposition_for("매물안내.pdf")
        self.assertEqual(mime, "application/pdf")
        self.assertEqual(disposition, "inline")
        mime, disposition = content_disposition_for("문서.svg")
        self.assertEqual(mime, "application/octet-stream")
        self.assertEqual(disposition, "attachment")


class DocumentStoreTests(unittest.TestCase):
    def test_save_list_download_delete_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "seen.sqlite3"
            save_document(db, "direct:1", "등기부등본.pdf", b"%PDF-1.4 fake")
            save_document(db, "direct:1", "사진.jpg", b"\xff\xd8 fake")

            docs = list_documents(db, "direct:1")
            self.assertEqual([d["name"] for d in docs], ["등기부등본.pdf", "사진.jpg"])
            self.assertTrue(all(d["size"] > 0 for d in docs))

            path = document_path(db, "direct:1", "등기부등본.pdf")
            self.assertTrue(path.read_bytes().startswith(b"%PDF"))
            self.assertIsNone(document_path(db, "direct:1", "없는파일.pdf"))

            counts = count_all_documents(db)
            self.assertEqual(counts["direct_1"], 2)

            self.assertTrue(delete_document(db, "direct:1", "사진.jpg"))
            self.assertFalse(delete_document(db, "direct:1", "사진.jpg"))

            delete_all_documents(db, "direct:1")
            self.assertEqual(list_documents(db, "direct:1"), [])

    def test_size_and_empty_limits(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Path(temp_dir) / "seen.sqlite3"
            with self.assertRaises(ValueError):
                save_document(db, "a:1", "빈파일.pdf", b"")
            with self.assertRaises(ValueError):
                save_document(db, "a:1", "큰파일.pdf", b"x" * (MAX_DOCUMENT_BYTES + 1))


if __name__ == "__main__":
    unittest.main()
