import base64
import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from unittest import mock

from realestate_alert.web_server import create_handler


class WebServerTests(unittest.TestCase):
    def setUp(self):
        # 좌표 캐시는 모듈 전역이라 테스트 간 오염을 막기 위해 매번 비운다.
        import realestate_alert.land_info as land_info

        land_info._geocode_cache.clear()

    def test_api_listings_returns_matching_listings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                response = _listings_when_ready(server)
            finally:
                server.shutdown()
                server.server_close()

        self.assertEqual(response["fetched_count"], 2)
        self.assertEqual(response["matched_count"], 1)
        self.assertEqual(response["listings"][0]["external_id"], "match")
        self.assertEqual(response["listings"][0]["registry_status"], "등기 확인 필요")
        self.assertTrue(response["listings"][0]["is_match"])
        self.assertEqual(len(response["unmatched_listings"]), 1)
        self.assertEqual(response["unmatched_listings"][0]["external_id"], "miss")
        self.assertFalse(response["unmatched_listings"][0]["is_match"])

    def test_listing_payload_never_blocks_on_geocoding(self):
        """HTTP 응답 경로(_listing_to_dict)는 캐시된 좌표만 읽고 동기 지오코딩하지 않는다."""
        from realestate_alert.web_server import _listing_to_dict
        from realestate_alert.models import Listing
        import realestate_alert.land_info as land_info

        land_info._geocode_cache.clear()
        listing = Listing(
            source="onbid", external_id="x", title="[공매] 양천구 상가",
            location="서울특별시 양천구 목동 1", deposit=0, monthly_rent=0,
            area_m2=0.0, floor=None, premium=None, url="https://www.onbid.co.kr",
        )
        # 캐시에 없으면 네트워크 호출 없이 None
        with mock.patch.object(land_info, "geocode_parcel", side_effect=AssertionError("동기 지오코딩 금지")):
            without_cache = _listing_to_dict(listing, with_coords=True)
        self.assertIsNone(without_cache["latitude"])
        # 백그라운드가 캐시를 채워두면 그 값을 읽는다
        land_info._geocode_cache[listing.location] = (37.5, 127.0)
        with_cache = _listing_to_dict(listing, with_coords=True)
        self.assertEqual(with_cache["latitude"], 37.5)
        self.assertEqual(with_cache["longitude"], 127.0)

    def test_api_listings_exposes_collection_progress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                response = _listings_when_ready(server)
            finally:
                server.shutdown()
                server.server_close()

        progress = response["progress"]
        self.assertIsNotNone(progress)
        self.assertEqual(progress["phase"], "done")
        self.assertEqual(progress["fetched"], 2)
        self.assertEqual(progress["sources_done"], progress["sources_total"])
        # 마지막 수집 시각이 채워져 화면에 "마지막 수집 HH:MM"으로 표시된다
        self.assertTrue(response["collected_at"])

    def test_api_diagnostics_reports_key_presence_and_source_counts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                # 진단 엔드포인트는 좌표 변환을 하지 않으므로 geocode 캐시를 더럽히지 않는다.
                with mock.patch.dict(
                    "os.environ",
                    {"DATA_GO_KR_API_KEY": "x" * 10},
                    clear=False,
                ):
                    diag = _diagnostics_when_ready(server)
            finally:
                server.shutdown()
                server.server_close()

        self.assertTrue(diag["keys"]["DATA_GO_KR_API_KEY"])
        self.assertEqual(diag["fetched_count"], 2)
        self.assertEqual(diag["source_counts"].get("manual"), 2)

    def test_api_config_exposes_kakao_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                with mock.patch.dict("os.environ", {"KAKAO_JS_KEY": "abc123"}, clear=False):
                    cfg = _request_json(server, "GET", "/api/config")
            finally:
                server.shutdown()
                server.server_close()
        self.assertEqual(cfg["kakao_js_key"], "abc123")

    def test_api_diagnostics_flags_missing_key(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items()
                         if k not in ("DATA_GO_KR_API_KEY", "VWORLD_API_KEY")}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    diag = _request_json(server, "GET", "/api/diagnostics")
            finally:
                server.shutdown()
                server.server_close()

        self.assertFalse(diag["keys"]["DATA_GO_KR_API_KEY"])
        self.assertFalse(diag["keys"]["VWORLD_API_KEY"])

    def test_api_scan_triggers_background_collection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                first = _request_json(server, "POST", "/api/scan")
                # 스캔이 끝나면 매물이 캐시에 채워진다
                listings = _listings_when_ready(server)
            finally:
                server.shutdown()
                server.server_close()

        self.assertTrue(first["scanning"])
        self.assertEqual(listings["matched_count"], 1)

    def test_api_listings_includes_naver_and_new_flags(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items()
                         if k not in ("DATA_GO_KR_API_KEY", "VWORLD_API_KEY")}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    response = _listings_when_ready(server)
            finally:
                server.shutdown()
                server.server_close()

        listing = response["listings"][0]
        self.assertIn("new.land.naver.com", listing["naver_land_url"])
        self.assertIn("map.naver.com", listing["naver_map_url"])
        self.assertTrue(listing["is_new"])
        self.assertFalse(listing["is_favorite"])
        self.assertEqual(response["new_count"], 1)
        # 키가 없으면 좌표는 None, 링크는 주소 검색 방식으로 동작한다
        self.assertIsNone(listing["latitude"])
        self.assertIsNone(listing["longitude"])

    def test_api_geocode_requires_address(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items()
                         if k not in ("DATA_GO_KR_API_KEY", "VWORLD_API_KEY")}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    result = _request_json(server, "GET", "/api/geocode?address=%EC%84%9C%EC%9A%B8")
                    with self.assertRaises(AssertionError):
                        _request_json(server, "GET", "/api/geocode")
            finally:
                server.shutdown()
                server.server_close()

        self.assertIsNone(result["latitude"])

    def test_api_favorites_toggle_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                payload = {
                    "identity": "manual:match",
                    "listing": {"title": "강남구 병원 가능 상가", "location": "서울 강남구 역삼동"},
                }
                first = _request_json(server, "POST", "/api/favorites/toggle", payload)
                favorites = _request_json(server, "GET", "/api/favorites")
                second = _request_json(server, "POST", "/api/favorites/toggle", payload)
                emptied = _request_json(server, "GET", "/api/favorites")
            finally:
                server.shutdown()
                server.server_close()

        self.assertTrue(first["is_favorite"])
        self.assertEqual(len(favorites["favorites"]), 1)
        self.assertFalse(second["is_favorite"])
        self.assertEqual(emptied["favorites"], [])

    def test_api_verify_reports_missing_keys_gracefully(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items()
                         if k not in ("DATA_GO_KR_API_KEY", "VWORLD_API_KEY")}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    report = _request_json(
                        server, "POST", "/api/verify",
                        {"address": "서울 양천구 목동 917-9", "months": 1},
                    )
            finally:
                server.shutdown()
                server.server_close()

        self.assertEqual(report["parcel"]["pnu"], "1147010100109170009")
        self.assertIn("building", report["errors"])
        self.assertIn("land", report["errors"])

    def test_api_ledger_upsert_and_delete(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                saved = _request_json(
                    server,
                    "POST",
                    "/api/ledger",
                    {
                        "identity": "manual:match",
                        "listing": {"title": "강남구 병원 가능 상가"},
                        "status": "방문 예정",
                        "memo": "다음주 화요일 방문",
                    },
                )
                entries = _request_json(server, "GET", "/api/ledger")
                deleted = _request_json(server, "POST", "/api/ledger/delete", {"identity": "manual:match"})
            finally:
                server.shutdown()
                server.server_close()

        self.assertEqual(saved["entry"]["status"], "방문 예정")
        self.assertEqual(len(entries["entries"]), 1)
        self.assertEqual(entries["entries"][0]["memo"], "다음주 화요일 방문")
        self.assertIn("검토중", entries["statuses"])
        self.assertTrue(deleted["deleted"])


class ChecklistApiTests(unittest.TestCase):
    def test_definition_endpoint(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                response = _request_json(server, "GET", "/api/checklist/definition")
            finally:
                server.shutdown()
                server.server_close()

        self.assertIn("building", response["profiles"])
        self.assertIn("rebuild", response["profiles"])
        self.assertTrue(any(item["item_id"] == "road_access" for item in response["items"]))

    def test_evaluate_and_manual_flow(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items()
                         if k not in ("DATA_GO_KR_API_KEY", "VWORLD_API_KEY")}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    evaluated = _request_json(
                        server, "POST", "/api/checklist/evaluate",
                        {
                            "identity": "manual:match",
                            "listing": {
                                "title": "후보",
                                "location": "서울 양천구 목동 917-9",
                                "zoning": "준주거지역",
                            },
                            "profile": "rebuild",
                        },
                    )
                    manual = _request_json(
                        server, "POST", "/api/checklist/manual",
                        {
                            "identity": "manual:match",
                            "item_id": "loc_overall",
                            "status": "pass",
                            "memo": "입지 양호",
                        },
                    )
                    reviews = _request_json(server, "GET", "/api/checklist/reviews")
                    single = _request_json(
                        server, "GET", "/api/checklist/review?identity=manual%3Amatch"
                    )
                    previewed = _request_json(
                        server,
                        "GET",
                        "/api/checklist/review?identity=manual%3Amatch&profile=building",
                    )
                    missing = _request_json(
                        server, "GET", "/api/checklist/review?identity=manual%3Anone"
                    )
            finally:
                server.shutdown()
                server.server_close()

        self.assertEqual(evaluated["review"]["profile"], "rebuild")
        zoning = next(i for i in evaluated["review"]["items"] if i["item_id"] == "zoning")
        self.assertEqual(zoning["status"], "pass")  # 키 없어도 listing.zoning 폴백
        self.assertIn("errors", evaluated)

        self.assertGreaterEqual(manual["review"]["progress"]["manual_done"], 1)
        loc = next(i for i in manual["review"]["items"] if i["item_id"] == "loc_overall")
        self.assertEqual(loc["memo"], "입지 양호")

        self.assertIn("manual:match", reviews["reviews"])
        self.assertEqual(reviews["reviews"]["manual:match"]["profile"], "rebuild")

        self.assertEqual(single["review"]["profile"], "rebuild")
        # 프로필 쿼리로 저장 없이 다른 프로필 미리보기 계산
        self.assertEqual(previewed["review"]["profile"], "building")
        self.assertIsNone(missing["review"])

    def test_manual_bulk_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                bulk = _request_json(
                    server, "POST", "/api/checklist/manual-bulk",
                    {
                        "identity": "a:1",
                        "status": "pass",
                        "item_ids": ["loc_overall", "loc_transit", "budget_total"],
                        "profile": "land",
                    },
                )
                reset = _request_json(
                    server, "POST", "/api/checklist/manual-bulk",
                    {
                        "identity": "a:1",
                        "status": "unchecked",
                        "item_ids": ["loc_overall"],
                    },
                )
                with self.assertRaises(AssertionError):
                    _request_json(
                        server, "POST", "/api/checklist/manual-bulk",
                        {"identity": "a:1", "status": "maybe", "item_ids": ["loc_overall"]},
                    )
                with self.assertRaises(AssertionError):
                    _request_json(
                        server, "POST", "/api/checklist/manual-bulk",
                        {"identity": "a:1", "status": "pass", "item_ids": ["nope"]},
                    )
            finally:
                server.shutdown()
                server.server_close()

        self.assertEqual(bulk["review"]["progress"]["manual_done"], 3)
        self.assertEqual(bulk["updated"], 3)
        self.assertEqual(reset["review"]["progress"]["manual_done"], 2)

    def test_auto_override_fills_card_and_survives_reevaluation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items()
                         if k not in ("DATA_GO_KR_API_KEY", "VWORLD_API_KEY")}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    # 키 없이 평가 → 용도지역 미확인
                    evaluated = _request_json(
                        server, "POST", "/api/checklist/evaluate",
                        {
                            "identity": "manual:match",
                            "listing": {"title": "후보", "location": "서울 양천구 목동 917-9"},
                            "profile": "building",
                        },
                    )
                    # 제공 자료 근거로 수동 입력
                    overridden = _request_json(
                        server, "POST", "/api/checklist/auto-override",
                        {
                            "identity": "manual:match",
                            "profile": "building",
                            "overrides": [
                                {"item_id": "zoning", "status": "pass", "evidence": "일반상업지역 — 의원 허용"},
                                {"item_id": "elevator", "status": "fail", "evidence": "승강기 없음 · 4층"},
                            ],
                        },
                    )
                    # 자동 검증을 다시 돌려도 수동 입력은 보존되어야 한다
                    reevaluated = _request_json(
                        server, "POST", "/api/checklist/evaluate",
                        {
                            "identity": "manual:match",
                            "listing": {"title": "후보", "location": "서울 양천구 목동 917-9"},
                            "profile": "building",
                        },
                    )
                    # 빈 상태로 보내면 수동 입력 해제
                    cleared = _request_json(
                        server, "POST", "/api/checklist/auto-override",
                        {
                            "identity": "manual:match",
                            "overrides": [{"item_id": "zoning", "status": "", "evidence": ""}],
                        },
                    )
            finally:
                server.shutdown()
                server.server_close()

        zoning0 = next(i for i in evaluated["review"]["items"] if i["item_id"] == "zoning")
        self.assertEqual(zoning0["status"], "unknown")

        self.assertEqual(overridden["updated"], 2)
        zoning1 = next(i for i in overridden["review"]["items"] if i["item_id"] == "zoning")
        self.assertEqual(zoning1["status"], "pass")
        self.assertEqual(zoning1["source"], "manual")
        self.assertIn("일반상업지역", zoning1["evidence"])

        zoning2 = next(i for i in reevaluated["review"]["items"] if i["item_id"] == "zoning")
        self.assertEqual(zoning2["status"], "pass")  # 재평가에도 수동 입력 유지
        self.assertEqual(zoning2["source"], "manual")

        zoning3 = next(i for i in cleared["review"]["items"] if i["item_id"] == "zoning")
        self.assertEqual(zoning3["status"], "unknown")  # 해제되어 자동값(미확인)으로 복귀
        self.assertEqual(zoning3["source"], "auto")

    def test_auto_override_rejects_non_overridable_and_bad_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                with self.assertRaises(AssertionError):
                    # loc_overall은 manual 항목 — 수동 입력(override) 불가
                    _request_json(
                        server, "POST", "/api/checklist/auto-override",
                        {"identity": "a:1", "overrides": [{"item_id": "loc_overall", "status": "pass"}]},
                    )
                with self.assertRaises(AssertionError):
                    _request_json(
                        server, "POST", "/api/checklist/auto-override",
                        {"identity": "a:1", "overrides": [{"item_id": "zoning", "status": "maybe"}]},
                    )
            finally:
                server.shutdown()
                server.server_close()

    def test_suggest_fills_cards_from_property_facts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items()
                         if k not in ("DATA_GO_KR_API_KEY", "VWORLD_API_KEY")}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    suggested = _request_json(
                        server, "POST", "/api/checklist/suggest",
                        {
                            "profile": "building",
                            "listing": {
                                "title": "세븐일레븐 신림패션점",
                                "location": "서울특별시 관악구 신림동 1431-1",
                            },
                            "facts": {
                                "zoning": "일반상업지역",
                                "approval_year": 1983,
                                "parking_spaces": 0,
                                "building_area_m2": 401.67,
                                "floors_total": 4,
                                "elevator": False,
                                "main_purpose": "유흥주점/소매점/사무소",
                            },
                        },
                    )
            finally:
                server.shutdown()
                server.server_close()

        auto = suggested["auto"]
        self.assertEqual(auto["zoning"]["status"], "pass")
        # 심평원 조회는 동 이름만 있으면 시도된다 — 키가 없어도 errors.medical로 안내된다.
        # (require_key가 네트워크 호출 전에 즉시 실패하므로 오프라인에서도 안전)
        self.assertIn("medical", suggested["errors"])
        self.assertIn("일반상업지역", auto["zoning"]["evidence"])
        self.assertEqual(auto["building_age"]["status"], "warn")
        self.assertEqual(auto["parking"]["status"], "warn")  # 주차 0 < 추정 법정 3
        self.assertEqual(auto["elevator"]["status"], "fail")  # 4층 + 승강기 없음
        self.assertEqual(auto["current_use"]["status"], "info")
        self.assertIn("유흥주점", auto["current_use"]["evidence"])

    def test_report_returns_structured_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items()
                         if k not in ("DATA_GO_KR_API_KEY", "VWORLD_API_KEY")}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    payload = _request_json(
                        server, "POST", "/api/report",
                        {
                            "identity": "manual:711",
                            "profile": "building",
                            "listing": {
                                "title": "세븐일레븐 신림패션점",
                                "location": "서울특별시 관악구 신림동 1431-1",
                                "zoning": "일반상업지역",
                                "approval_year": 1983,
                            },
                        },
                    )
            finally:
                server.shutdown()
                server.server_close()

        # 리포트 렌더에 필요한 키들이 모두 존재해야 한다
        for key in ("listing", "parcel", "building", "land", "market", "medical", "review", "errors", "generated_at"):
            self.assertIn(key, payload)
        self.assertIn("items", payload["review"])
        self.assertEqual(payload["listing"]["title"], "세븐일레븐 신림패션점")
        # listing 폴백으로 용도지역은 적합 판정
        zoning = next(i for i in payload["review"]["items"] if i["item_id"] == "zoning")
        self.assertEqual(zoning["status"], "pass")

    def test_manual_rejects_bad_status_and_item(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                with self.assertRaises(AssertionError):
                    _request_json(
                        server, "POST", "/api/checklist/manual",
                        {"identity": "a:1", "item_id": "loc_overall", "status": "maybe"},
                    )
                with self.assertRaises(AssertionError):
                    _request_json(
                        server, "POST", "/api/checklist/manual",
                        {"identity": "a:1", "item_id": "nope", "status": "pass"},
                    )
                with self.assertRaises(AssertionError):
                    _request_json(
                        server, "POST", "/api/checklist/evaluate",
                        {"identity": "a:1", "listing": {"title": "주소 없음"}, "profile": "building"},
                    )
            finally:
                server.shutdown()
                server.server_close()

    def test_listings_include_first_seen_at(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                _request_json(server, "POST", "/api/scan")
                response = _listings_when_ready(server)
            finally:
                server.shutdown()
                server.server_close()

        self.assertIn("first_seen_at", response["listings"][0])
        self.assertTrue(response["listings"][0]["first_seen_at"])


class DashboardAuthTests(unittest.TestCase):
    def test_password_protects_api_and_static(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                with mock.patch.dict("os.environ", {"DASHBOARD_PASSWORD": "secret210"}):
                    with self.assertRaises(AssertionError):
                        _request_json(server, "GET", "/api/listings")
                    with self.assertRaises(AssertionError):
                        _request_json(
                            server, "GET", "/api/listings",
                            headers=_basic_auth("210", "wrong-password"),
                        )
                    ok = _request_json(
                        server, "GET", "/api/listings",
                        headers=_basic_auth("아무거나", "secret210"),
                    )
            finally:
                server.shutdown()
                server.server_close()

        self.assertIn("listings", ok)

    def test_no_password_means_open_local_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            clean_env = {k: v for k, v in os.environ.items() if k != "DASHBOARD_PASSWORD"}
            try:
                with mock.patch.dict("os.environ", clean_env, clear=True):
                    response = _request_json(server, "GET", "/api/ledger")
            finally:
                server.shutdown()
                server.server_close()

        self.assertIn("entries", response)


class DocumentApiTests(unittest.TestCase):
    def test_upload_list_download_and_ledger_cascade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                _request_json(server, "POST", "/api/ledger", {
                    "identity": "direct:1", "listing": {"title": "부동산 소개 매물"},
                })
                uploaded = _request_json(
                    server, "POST",
                    "/api/documents/upload?identity=direct%3A1&name=%EB%93%B1%EA%B8%B0%EB%B6%80.pdf",
                    raw_body=b"%PDF-1.4 fake-doc",
                )
                listed = _request_json(server, "GET", "/api/documents?identity=direct%3A1")
                status, headers, body = _request_raw(
                    server, "GET",
                    "/api/documents/file?identity=direct%3A1&name=%EB%93%B1%EA%B8%B0%EB%B6%80.pdf",
                )
                counts = _request_json(server, "GET", "/api/documents/counts")
                # 매물장 삭제 시 서류도 함께 삭제
                _request_json(server, "POST", "/api/ledger/delete", {"identity": "direct:1"})
                emptied = _request_json(server, "GET", "/api/documents?identity=direct%3A1")
            finally:
                server.shutdown()
                server.server_close()

        self.assertEqual(uploaded["documents"][0]["name"], "등기부.pdf")
        self.assertEqual(len(listed["documents"]), 1)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Content-Type"), "application/pdf")
        self.assertTrue(body.startswith(b"%PDF"))
        self.assertEqual(counts["counts"].get("direct_1"), 1)
        self.assertEqual(emptied["documents"], [])

    def test_upload_rejects_traversal_and_oversize(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = _write_fixture_config(root)
            server = _start_server(config_path, root)
            try:
                with self.assertRaises(AssertionError):
                    _request_json(
                        server, "POST",
                        "/api/documents/upload?identity=a%3A1&name=..",
                        raw_body=b"data",
                    )
                with self.assertRaises(AssertionError):
                    _request_json(
                        server, "POST",
                        "/api/documents/upload?identity=a%3A1&name=ok.pdf",
                        raw_body=b"",
                    )
            finally:
                server.shutdown()
                server.server_close()


def _diagnostics_when_ready(server: ThreadingHTTPServer, attempts: int = 50) -> dict:
    """진단 엔드포인트를 수집 완료까지 폴링한다 (좌표 변환 없이 캐시만 채운다)."""
    import time as _time

    response = _request_json(server, "GET", "/api/diagnostics")
    for _ in range(attempts):
        if response.get("fetched_count", 0) > 0:
            return response
        _time.sleep(0.05)
        response = _request_json(server, "GET", "/api/diagnostics")
    return response


def _listings_when_ready(server: ThreadingHTTPServer, attempts: int = 50) -> dict:
    """수집은 백그라운드라 캐시가 찰 때까지 /api/listings를 폴링한다 (테스트 픽스처는 즉시 완료)."""
    import time as _time

    response = _request_json(server, "GET", "/api/listings")
    for _ in range(attempts):
        if response.get("fetched_count", 0) > 0 or not response.get("collecting"):
            if response.get("fetched_count", 0) > 0:
                return response
        _time.sleep(0.05)
        response = _request_json(server, "GET", "/api/listings")
    return response


def _request_raw(
    server: ThreadingHTTPServer, method: str, path: str
) -> tuple[int, dict, bytes]:
    connection = http.client.HTTPConnection(server.server_address[0], server.server_address[1], timeout=5)
    try:
        connection.request(method, path)
        response = connection.getresponse()
        body = response.read()
        return response.status, dict(response.getheaders()), body
    finally:
        connection.close()


def _basic_auth(user: str, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def _write_fixture_config(root: Path) -> Path:
    listings_path = root / "listings.json"
    listings_path.write_text(
        json.dumps(
            [
                {
                    "source": "manual",
                    "external_id": "match",
                    "title": "강남구 병원 가능 상가",
                    "location": "서울 강남구 역삼동",
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
                    "floor": "1층",
                    "premium": 0,
                    "url": "https://example.test/miss",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    config_path = root / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "database_path": str(root / "seen.sqlite3"),
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
    return config_path


def _start_server(config_path: Path, web_root: Path) -> ThreadingHTTPServer:
    handler = create_handler(config_path=config_path, web_root=web_root)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _request_json(
    server: ThreadingHTTPServer,
    method: str,
    path: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    raw_body: bytes | None = None,
) -> dict:
    connection = http.client.HTTPConnection(server.server_address[0], server.server_address[1], timeout=5)
    try:
        body_bytes = None
        headers = dict(headers or {})
        if payload is not None:
            body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        elif raw_body is not None:
            body_bytes = raw_body
            headers["Content-Type"] = "application/octet-stream"
        connection.request(method, path, body=body_bytes, headers=headers)
        response = connection.getresponse()
        body = response.read().decode("utf-8")
    finally:
        connection.close()
    if response.status != 200:
        raise AssertionError(f"Expected 200, got {response.status}: {body}")
    return json.loads(body)
