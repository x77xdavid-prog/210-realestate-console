"""운영 안정화(Render 영구 디스크) 관련 회귀 테스트.

- export-registry-targets 의 상대 출력이 config 폴더가 아니라 database_path(데이터 디스크)
  폴더 기준으로 해석되는지(재배포 유실 방지).
- 시작 배너 report_startup_persistence 가 데이터 경로를 출력하고, Render에서 영구 디스크
  밖이면 경고하는지.
"""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from realestate_alert.cli import main
from realestate_alert.web_server import persistence_warning, report_startup_persistence


def _write_config(root: Path, data_dir: Path) -> Path:
    """config 폴더와 database_path 폴더를 일부러 다르게 둔 설정을 만든다."""
    listings_path = root / "listings.json"
    listings_path.write_text(
        json.dumps(
            [
                {
                    "source": "manual",
                    "external_id": "m1",
                    "title": "강남구 병원 가능 상가",
                    "location": "서울 강남구 역삼동",
                    "deposit": 10000000,
                    "monthly_rent": 1000000,
                    "area_m2": 90,
                    "url": "https://example.test/m1",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config_path = root / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "database_path": str(data_dir / "seen.sqlite3"),
                "criteria": {"locations": [], "required_keywords": []},
                "sources": [{"type": "json_file", "path": str(listings_path)}],
                "notifiers": [{"type": "console"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return config_path


class RegistryOutputPathTests(unittest.TestCase):
    def test_relative_output_resolves_under_database_dir_not_config_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "disk"  # database_path 의 부모 (= Render의 /data 대응)
            config_path = _write_config(root, data_dir)

            rc = main(["export-registry-targets", "--config", str(config_path)])

            self.assertEqual(rc, 0)
            # 데이터 디스크 폴더에 생성돼야 한다.
            self.assertTrue((data_dir / "registry-targets.csv").exists())
            # config 폴더(root)에는 생성되면 안 된다(예전 동작 = 휘발성).
            self.assertFalse((root / "registry-targets.csv").exists())


class StartupBannerTests(unittest.TestCase):
    def _run(self, config_path: Path, env: dict) -> str:
        buf = io.StringIO()
        with mock.patch.dict("os.environ", env, clear=False):
            with redirect_stdout(buf):
                report_startup_persistence(config_path)
        return buf.getvalue()

    def test_banner_prints_data_dir_and_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "disk"
            config_path = _write_config(root, data_dir)

            out = self._run(config_path, env={})

            self.assertIn("[persistence]", out)
            self.assertIn(str(data_dir), out)
            self.assertIn("writable", out)

    def test_warns_when_on_render_and_outside_data_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "disk"  # /data 가 아님
            config_path = _write_config(root, data_dir)

            out = self._run(config_path, env={"RENDER": "true"})

            self.assertIn("경고", out)
            self.assertIn("config.render.json", out)

    def test_no_warning_when_not_on_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "disk"
            config_path = _write_config(root, data_dir)

            # RENDER 미설정 — 로컬에서 임의 경로를 써도 경고하지 않는다.
            out = self._run(config_path, env={})

            self.assertNotIn("경고", out)


class PersistenceWarningLogicTests(unittest.TestCase):
    def test_not_on_render_never_warns(self):
        self.assertIsNone(persistence_warning("/somewhere/else", on_render=False, writable=True))
        self.assertIsNone(persistence_warning("/somewhere/else", on_render=False, writable=False))

    def test_on_render_happy_path_no_warning(self):
        # 경로 /data + 디스크 마운트됨 + 쓰기 가능 = 정상
        self.assertIsNone(persistence_warning("/data", on_render=True, writable=True, disk_mounted=True))
        self.assertIsNone(persistence_warning("/data/sub", on_render=True, writable=True, disk_mounted=True))

    def test_on_render_outside_disk_warns(self):
        self.assertEqual(persistence_warning("/app/data", on_render=True, writable=True), "outside-disk")
        self.assertEqual(persistence_warning("/opt/render/project/src/data", on_render=True, writable=True), "outside-disk")

    def test_on_render_path_ok_but_no_disk_mounted(self):
        # config 는 맞지만 /data 에 디스크가 안 붙은 핵심 케이스 → no-disk
        self.assertEqual(
            persistence_warning("/data", on_render=True, writable=True, disk_mounted=False),
            "no-disk",
        )

    def test_no_disk_takes_precedence_over_writable(self):
        self.assertEqual(
            persistence_warning("/data", on_render=True, writable=False, disk_mounted=False),
            "no-disk",
        )

    def test_unknown_mount_does_not_force_no_disk(self):
        # 마운트 여부 판단 불가(None)면 no-disk 경고를 띄우지 않는다(쓰기만 본다).
        self.assertIsNone(persistence_warning("/data", on_render=True, writable=True, disk_mounted=None))

    def test_on_render_on_disk_but_not_writable(self):
        self.assertEqual(
            persistence_warning("/data", on_render=True, writable=False, disk_mounted=True),
            "not-writable",
        )

    def test_prefix_boundary_not_treated_as_data_disk(self):
        # /database, /datastore 등은 /data 가 아니므로 휘발성으로 경고해야 한다.
        self.assertEqual(persistence_warning("/database", on_render=True, writable=True), "outside-disk")
        self.assertEqual(persistence_warning("/datastore/x", on_render=True, writable=True), "outside-disk")

    def test_windows_backslash_normalized(self):
        self.assertIsNone(persistence_warning("\\data\\photos", on_render=True, writable=True))


if __name__ == "__main__":
    unittest.main()
