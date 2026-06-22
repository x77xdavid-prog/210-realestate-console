from __future__ import annotations

import base64
import hmac
import json
import os
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from realestate_alert.address import extract_dong
from realestate_alert.checklist import (
    AUTO_STATUSES,
    ITEM_IDS,
    MANUAL_STATUSES,
    OVERRIDABLE_ITEM_IDS,
    PROFILES,
    compute_review,
    definition_payload,
    evaluate_auto_items,
)
from realestate_alert.config import load_config
from realestate_alert.documents import (
    MAX_DOCUMENT_BYTES,
    content_disposition_for,
    count_all_documents,
    delete_all_documents,
    delete_document,
    document_path,
    list_documents,
    save_document,
)
from realestate_alert.land_info import cached_coords, geocode_parcel
from realestate_alert.medical_nearby import fetch_medical_nearby, medical_to_dict
from realestate_alert.models import Listing
from realestate_alert.naver import naver_land_coord_url, naver_land_url, naver_map_url
from realestate_alert.public_data import PublicDataError
from realestate_alert.registry import RegistryStatus
from realestate_alert.filtering import matches_listing
from realestate_alert.hospital_fit import classify as classify_hospital_fit
from realestate_alert.service import ListingSnapshot, collect_listings, run_once
from realestate_alert.store import LEDGER_STATUSES, ListingStore
from realestate_alert.verify import market_for_address, verify_address

MAX_BODY_BYTES = 256 * 1024

# 한 소스(예: 클라우드의 느린 법원경매)가 전체 수집을 무한정 막지 못하도록 하는 마감 시간.
# 이 시간을 넘긴 소스는 이번 주기에서 제외하고, 끝난 소스만으로 결과를 낸다.
COLLECT_DEADLINE_SECONDS = 60
# 일부 소스가 마감으로 빠졌을 때(미완료) 다음 재시도까지의 대기(정상 TTL보다 짧게).
RETRY_SOON_SECONDS = 90

# 설정 시 모든 요청에 브라우저 기본 로그인(아이디 무관, 비밀번호 일치)을 요구한다.
# 로컬 전용 사용이면 비워 두면 된다 — 클라우드 공개 배포 시 필수.
DASHBOARD_PASSWORD_ENV = "DASHBOARD_PASSWORD"

# 수집 결과 캐시 — HTTP 요청은 절대 수집을 기다리지 않고 캐시만 읽는다.
# 수집은 백그라운드 스레드가 처리한다 (저사양 클라우드에서 요청 타임아웃/OOM 방지).
_snapshot_cache: dict[str, ListingSnapshot] = {}
_snapshot_fetched_at: dict[str, float] = {}
_snapshot_collected_at: dict[str, str] = {}  # 마지막 수집 완료 시각(UTC ISO) — 화면 표시용
_collect_lock = threading.Lock()
_collecting: set[str] = set()
# 수집 진행 상황 — 대시보드가 "수집 갯수 올라가는" 연출을 보여주기 위해 폴링해 읽는다.
_collect_progress: dict[str, dict[str, Any]] = {}


def _empty_snapshot() -> ListingSnapshot:
    return ListingSnapshot(fetched=[], matched=[])


def _count_sources(listings: list[Listing]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for listing in listings:
        counts[listing.source] = counts.get(listing.source, 0) + 1
    return counts


def _collect_with_progress(config_path: Path, config) -> tuple[ListingSnapshot, bool]:
    """수집 + 좌표 워밍을 진행률을 기록하며 수행한다(백그라운드 전용).

    - 수집 단계: 소스가 끝날 때마다 진행률을 갱신하고, 끝난 소스 결과를 캐시에 즉시 반영한다
      (느린 소스를 기다리지 않고 빠른 소스부터 화면에 보이도록).
    - 좌표 변환 단계: 매물 1건마다 진행률을 갱신한다.
    HTTP 핸들러는 이 진행률(_collect_progress)을 읽기만 하고 절대 수집/지오코딩하지 않는다.
    반환: (스냅샷, 전체 소스 완료 여부) — 마감으로 일부 소스가 빠졌으면 False.
    """
    key = str(config_path)
    total_sources = len(config.sources)
    _collect_progress[key] = {
        "phase": "collecting", "fetched": 0, "by_source": {},
        "sources_done": 0, "sources_total": total_sources,
        "geocoded": 0, "geocode_total": 0,
    }

    def on_progress(fetched: list[Listing], done: int, total: int) -> None:
        _collect_progress[key] = {
            "phase": "collecting", "fetched": len(fetched),
            "by_source": _count_sources(fetched),
            "sources_done": done, "sources_total": total,
            "geocoded": 0, "geocode_total": 0,
        }
        # 끝난 소스 결과를 즉시 캐시에 반영 — 느린 소스(법원경매)를 기다리지 않는다.
        matched = [item for item in fetched if matches_listing(config.criteria, item)]
        _snapshot_cache[key] = ListingSnapshot(fetched=list(fetched), matched=matched)

    snapshot = collect_listings(
        config, on_progress=on_progress, deadline_seconds=COLLECT_DEADLINE_SECONDS
    )
    sources_done = _collect_progress[key].get("sources_done", 0)
    complete = sources_done >= total_sources

    # 데이터가 다 모였으니 즉시 '완료' 처리한다 — 스피너가 좌표 변환까지 기다리지 않게.
    # (좌표 변환은 _run_collection이 완료 처리 후 백그라운드로 따로 채운다)
    _collect_progress[key] = {
        "phase": "done", "fetched": snapshot.fetched_count,
        "by_source": _count_sources(snapshot.fetched),
        "sources_done": sources_done, "sources_total": total_sources,
        "geocoded": snapshot.matched_count, "geocode_total": snapshot.matched_count,
    }
    return snapshot, complete


def _warm_match_coords(listings: list[Listing]) -> None:
    """조건 일치 매물의 좌표를 캐시에 채운다(백그라운드 — 스피너/완료와 무관).

    HTTP 응답은 cached_coords로 캐시만 읽으므로, 워밍 전이면 핀이 없고 다음 새로고침에 나타난다.
    """
    for listing in listings:
        _safe_geocode(listing.location)


def _store_snapshot(key: str, snapshot: ListingSnapshot, config, complete: bool) -> None:
    """수집 결과를 캐시에 저장한다. 일부 소스가 빠졌으면 더 일찍 재시도하도록 시각을 조정."""
    _snapshot_cache[key] = snapshot
    _snapshot_collected_at[key] = _utc_now_iso()
    if complete:
        _snapshot_fetched_at[key] = time.monotonic()
    else:
        ttl = max(60, config.interval_seconds)
        _snapshot_fetched_at[key] = time.monotonic() - ttl + RETRY_SOON_SECONDS


def _run_collection(config_path: Path) -> None:
    """백그라운드에서 수집해 캐시를 채운다. 동시 중복 수집은 막는다."""
    key = str(config_path)
    with _collect_lock:
        if key in _collecting:
            return
        _collecting.add(key)
    try:
        config = load_config(config_path)
        snapshot, complete = _collect_with_progress(config_path, config)
        _store_snapshot(key, snapshot, config, complete)
        # 완료 표시 후 좌표를 천천히 채운다(스피너와 무관, 지도 핀은 다음 새로고침에 표시).
        _warm_match_coords(snapshot.matched)
    except Exception as error:  # noqa: BLE001 — 수집 실패는 다음 주기에 재시도
        print(f"[collect] 백그라운드 수집 실패: {error}")
    finally:
        _collecting.discard(key)


def _ensure_collection(config_path: Path, force: bool = False) -> bool:
    """캐시가 비었거나 오래됐으면(또는 force) 백그라운드 수집을 띄운다. 진행 중이면 True."""
    key = str(config_path)
    ttl = max(60, load_config(config_path).interval_seconds)
    fetched_at = _snapshot_fetched_at.get(key, 0.0)
    stale = (time.monotonic() - fetched_at) >= ttl
    if force or key not in _snapshot_cache or stale:
        threading.Thread(target=_run_collection, args=(config_path,), daemon=True).start()
    return key in _collecting


def _cached_snapshot(config_path: Path) -> ListingSnapshot:
    """캐시 스냅샷을 즉시 반환한다(없으면 빈 스냅샷). 갱신은 백그라운드에 맡긴다."""
    _ensure_collection(config_path)
    return _snapshot_cache.get(str(config_path)) or _empty_snapshot()


def _invalidate_snapshot(config_path: Path) -> None:
    _snapshot_fetched_at.pop(str(config_path), None)


def _run_scan(config_path: Path) -> None:
    """백그라운드 전체 스캔 — 수집 + 신규 매물 알림 + 캐시 갱신."""
    key = str(config_path)
    with _collect_lock:
        if key in _collecting:
            return
        _collecting.add(key)
    try:
        config = load_config(config_path)
        # 진행률을 보여주며 한 번만 수집하고, 그 스냅샷을 알림·캐시에 함께 쓴다(중복 수집 제거).
        snapshot, complete = _collect_with_progress(config_path, config)
        result = run_once(config, snapshot=snapshot)
        _store_snapshot(key, snapshot, config, complete)
        _warm_match_coords(snapshot.matched)
        print(f"[scan] 완료 — 수집 {result.fetched_count} / 신규 {len(result.notified)}")
    except Exception as error:  # noqa: BLE001
        print(f"[scan] 백그라운드 스캔 실패: {error}")
    finally:
        _collecting.discard(key)


def _start_scan(config_path: Path) -> bool:
    """스캔을 백그라운드로 시작한다. 이미 진행 중이면 False."""
    key = str(config_path)
    if key in _collecting:
        return False
    threading.Thread(target=_run_scan, args=(config_path,), daemon=True).start()
    return True


def create_handler(config_path: Path, web_root: Path) -> type[SimpleHTTPRequestHandler]:
    class RealEstateAlertHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web_root), **kwargs)

        def do_GET(self) -> None:
            if not self._authorized():
                self._send_unauthorized()
                return
            if self.path == "/api/listings":
                self._send_json(_listings_payload(config_path))
                return
            if self.path.startswith("/api/listing/detail"):
                q = parse_qs(urlparse(self.path).query)
                identity = (q.get("id") or [""])[0]
                cs_no = (q.get("cs") or [""])[0]
                cort = (q.get("court") or [""])[0]
                seq = (q.get("seq") or ["1"])[0]
                if not identity:
                    self._send_json({"error": "id 필요"}, status=400); return
                payload = build_detail_payload(_store(config_path), identity, cs_no, cort, seq,
                                               photo_dir=_photo_dir(config_path))
                self._send_json(payload); return
            if self.path.startswith("/api/listing/doc-link"):
                q = parse_qs(urlparse(self.path).query)
                cs_no = (q.get("cs") or [""])[0]
                cort = (q.get("court") or [""])[0]
                seq = (q.get("seq") or ["1"])[0]
                kind = (q.get("kind") or ["sale_spec"])[0]
                if not cs_no or not cort:
                    self._send_json({"url": None, "error": "cs/court 필요"}, status=400)
                    return
                from realestate_alert.court_documents import sale_spec_viewer_url
                url = sale_spec_viewer_url(cs_no, cort, seq) if kind == "sale_spec" else None
                self._send_json({"url": url})
                return
            if self.path.startswith("/api/listing/tenants"):
                q = parse_qs(urlparse(self.path).query)
                cs_no = (q.get("cs") or [""])[0]
                cort = (q.get("court") or [""])[0]
                if not cs_no or not cort:
                    self._send_json({"tenants": [], "occupancy": [], "survey": {},
                                     "error": "cs/court 필요"}, status=400)
                    return
                from realestate_alert.court_curst import fetch_tenants
                self._send_json(fetch_tenants(cs_no, cort))
                return
            if self.path.startswith("/api/photo"):
                q = parse_qs(urlparse(self.path).query)
                target = safe_photo_path(_photo_dir(config_path), (q.get("path") or [""])[0])
                if not target or not target.exists():
                    self.send_response(404); self.end_headers(); return
                data = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers(); self.wfile.write(data); return
            if self.path == "/api/diagnostics":
                self._send_json(_diagnostics_payload(config_path))
                return
            if self.path == "/api/config":
                # Kakao 지도 JS 키(도메인 제한 클라이언트 키)를 프런트에 전달. 없으면 빈 문자열.
                self._send_json({"kakao_js_key": os.environ.get("KAKAO_JS_KEY", "").strip()})
                return
            if self.path.startswith("/api/geocode"):
                query = parse_qs(urlparse(self.path).query)
                address = (query.get("address") or [""])[0].strip()
                if not address:
                    self._send_json({"error": "address가 필요합니다."}, status=400)
                    return
                coords = _safe_geocode(address)
                self._send_json(
                    {
                        "address": address,
                        "latitude": coords[0] if coords else None,
                        "longitude": coords[1] if coords else None,
                    }
                )
                return
            if self.path == "/api/favorites":
                self._send_json({"favorites": _store(config_path).list_favorites()})
                return
            if self.path == "/api/ledger":
                self._send_json(
                    {
                        "entries": _store(config_path).list_ledger_entries(),
                        "statuses": LEDGER_STATUSES,
                    }
                )
                return
            if self.path == "/api/documents/counts":
                database_path = load_config(config_path).database_path
                self._send_json({"counts": count_all_documents(database_path)})
                return
            if self.path.startswith("/api/documents/file"):
                query = parse_qs(urlparse(self.path).query)
                identity = (query.get("identity") or [""])[0].strip()
                name = (query.get("name") or [""])[0].strip()
                if not identity or not name:
                    self._send_json({"error": "identity와 name이 필요합니다."}, status=400)
                    return
                try:
                    target = document_path(load_config(config_path).database_path, identity, name)
                except ValueError as error:
                    self._send_json({"error": str(error)}, status=400)
                    return
                if target is None:
                    self._send_json({"error": "서류를 찾을 수 없습니다."}, status=404)
                    return
                content = target.read_bytes()
                mime, disposition = content_disposition_for(target.name)
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header(
                    "Content-Disposition",
                    f"{disposition}; filename*=UTF-8''{quote(target.name)}",
                )
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            if self.path.startswith("/api/documents"):
                query = parse_qs(urlparse(self.path).query)
                identity = (query.get("identity") or [""])[0].strip()
                if not identity:
                    self._send_json({"error": "identity가 필요합니다."}, status=400)
                    return
                try:
                    documents = list_documents(load_config(config_path).database_path, identity)
                except ValueError as error:
                    self._send_json({"error": str(error)}, status=400)
                    return
                self._send_json({"identity": identity, "documents": documents})
                return
            if self.path == "/api/checklist/definition":
                self._send_json(definition_payload())
                return
            if self.path == "/api/checklist/reviews":
                self._send_json({"reviews": _review_summaries(config_path)})
                return
            if self.path.startswith("/api/checklist/review"):
                query = parse_qs(urlparse(self.path).query)
                identity = (query.get("identity") or [""])[0].strip()
                if not identity:
                    self._send_json({"error": "identity가 필요합니다."}, status=400)
                    return
                stored = _store(config_path).get_checklist_review(identity)
                review = None
                if stored:
                    # 프로필 전환 미리보기: 저장 없이 다른 프로필로 계산만 한다
                    override = (query.get("profile") or [""])[0].strip()
                    profile = override if override in PROFILES else stored["profile"]
                    review = compute_review(
                        profile,
                        stored.get("auto"),
                        stored.get("manual"),
                        stored.get("auto_override"),
                    )
                self._send_json({"identity": identity, "review": review})
                return
            if self.path == "/":
                self.path = "/index.html"
            super().do_GET()

        def do_POST(self) -> None:
            if not self._authorized():
                self._send_unauthorized()
                return
            if self.path == "/api/scan":
                # 수집·알림은 백그라운드에서 — 저사양 클라우드에서 요청이 막히지 않도록.
                started = _start_scan(config_path)
                snapshot = _snapshot_cache.get(str(config_path)) or _empty_snapshot()
                self._send_json(
                    {
                        "scanning": started,
                        "fetched_count": snapshot.fetched_count,
                        "matched_count": snapshot.matched_count,
                        "notified_count": 0,
                        "notified": [],
                    }
                )
                return
            if self.path == "/api/favorites/toggle":
                body = self._read_json_body()
                identity = str(body.get("identity", "")).strip()
                listing = body.get("listing")
                if not identity or not isinstance(listing, dict):
                    self._send_json({"error": "identity와 listing이 필요합니다."}, status=400)
                    return
                is_favorite = _store(config_path).toggle_favorite(identity, listing)
                self._send_json({"identity": identity, "is_favorite": is_favorite})
                return
            if self.path == "/api/ledger":
                body = self._read_json_body()
                identity = str(body.get("identity", "")).strip()
                listing = body.get("listing")
                status = str(body.get("status", LEDGER_STATUSES[0]))
                memo = str(body.get("memo", ""))
                if not identity or not isinstance(listing, dict):
                    self._send_json({"error": "identity와 listing이 필요합니다."}, status=400)
                    return
                if status not in LEDGER_STATUSES:
                    self._send_json({"error": f"지원하지 않는 상태: {status}"}, status=400)
                    return
                entry = _store(config_path).upsert_ledger_entry(identity, listing, status, memo)
                self._send_json({"entry": entry})
                return
            if self.path == "/api/verify":
                body = self._read_json_body()
                address = str(body.get("address", "")).strip()
                if not address:
                    self._send_json({"error": "address가 필요합니다."}, status=400)
                    return
                months = body.get("months", 6)
                if not isinstance(months, int) or not (1 <= months <= 12):
                    months = 6
                self._send_json(verify_address(address, market_months=months))
                return
            if self.path == "/api/market":
                body = self._read_json_body()
                address = str(body.get("address", "")).strip()
                if not address:
                    self._send_json({"error": "address가 필요합니다."}, status=400)
                    return
                months = body.get("months", 6)
                if not isinstance(months, int) or not (1 <= months <= 12):
                    months = 6
                self._send_json(market_for_address(address, market_months=months))
                return
            if self.path == "/api/ledger/delete":
                body = self._read_json_body()
                identity = str(body.get("identity", "")).strip()
                if not identity:
                    self._send_json({"error": "identity가 필요합니다."}, status=400)
                    return
                deleted = _store(config_path).delete_ledger_entry(identity)
                try:
                    # 매물장에서 빠지면 받은 서류도 함께 정리한다
                    delete_all_documents(load_config(config_path).database_path, identity)
                except ValueError:
                    pass  # 식별자가 폴더명으로 변환 불가한 경우 — 보관된 서류도 없음
                self._send_json({"identity": identity, "deleted": deleted})
                return
            if self.path.startswith("/api/documents/upload"):
                query = parse_qs(urlparse(self.path).query)
                identity = (query.get("identity") or [""])[0].strip()
                name = (query.get("name") or [""])[0].strip()
                if not identity or not name:
                    self._send_json({"error": "identity와 name이 필요합니다."}, status=400)
                    return
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                except ValueError:
                    length = 0
                if length <= 0:
                    self._send_json({"error": "빈 파일은 업로드할 수 없습니다."}, status=400)
                    return
                if length > MAX_DOCUMENT_BYTES:
                    self._send_json(
                        {"error": f"파일이 {MAX_DOCUMENT_BYTES // (1024 * 1024)}MB 제한을 초과합니다."},
                        status=413,
                    )
                    return
                content = self.rfile.read(length)
                database_path = load_config(config_path).database_path
                try:
                    save_document(database_path, identity, name, content)
                except ValueError as error:
                    self._send_json({"error": str(error)}, status=400)
                    return
                self._send_json(
                    {"identity": identity, "documents": list_documents(database_path, identity)}
                )
                return
            if self.path == "/api/documents/delete":
                body = self._read_json_body()
                identity = str(body.get("identity", "")).strip()
                name = str(body.get("name", "")).strip()
                if not identity or not name:
                    self._send_json({"error": "identity와 name이 필요합니다."}, status=400)
                    return
                database_path = load_config(config_path).database_path
                try:
                    removed = delete_document(database_path, identity, name)
                except ValueError as error:
                    self._send_json({"error": str(error)}, status=400)
                    return
                self._send_json(
                    {
                        "identity": identity,
                        "deleted": removed,
                        "documents": list_documents(database_path, identity),
                    }
                )
                return
            if self.path == "/api/checklist/evaluate":
                body = self._read_json_body()
                identity = str(body.get("identity", "")).strip()
                listing = body.get("listing")
                profile = str(body.get("profile", "building"))
                if not identity or not isinstance(listing, dict):
                    self._send_json({"error": "identity와 listing이 필요합니다."}, status=400)
                    return
                if profile not in PROFILES:
                    self._send_json({"error": f"지원하지 않는 프로필: {profile}"}, status=400)
                    return
                address = str(listing.get("location", "")).strip()
                if not address:
                    self._send_json({"error": "listing.location(주소)이 필요합니다."}, status=400)
                    return
                report = verify_address(address)
                _attach_medical_data(report)
                auto = evaluate_auto_items(listing, report)
                store = _store(config_path)
                stored = store.get_checklist_review(identity) or {}
                review = {
                    "profile": profile,
                    "auto": auto,
                    "manual": stored.get("manual", {}),
                    "auto_override": stored.get("auto_override", {}),
                    "evaluated_at": _utc_now_iso(),
                }
                store.save_checklist_review(identity, review)
                self._send_json(
                    {
                        "identity": identity,
                        "review": compute_review(
                            profile, auto, review["manual"], review["auto_override"]
                        ),
                        "errors": report.get("errors", {}),
                        "evaluated_at": review["evaluated_at"],
                    }
                )
                return
            if self.path == "/api/checklist/manual-bulk":
                body = self._read_json_body()
                identity = str(body.get("identity", "")).strip()
                status = str(body.get("status", "")).strip()
                item_ids = body.get("item_ids")
                if not identity or not isinstance(item_ids, list) or not item_ids:
                    self._send_json({"error": "identity와 item_ids(목록)가 필요합니다."}, status=400)
                    return
                if status not in MANUAL_STATUSES:
                    self._send_json({"error": f"지원하지 않는 체크 상태: {status}"}, status=400)
                    return
                unknown_ids = [item for item in item_ids if item not in ITEM_IDS]
                if unknown_ids:
                    self._send_json({"error": f"알 수 없는 체크 항목: {', '.join(map(str, unknown_ids))}"}, status=400)
                    return
                store = _store(config_path)
                stored = store.get_checklist_review(identity) or {
                    "profile": "building",
                    "auto": {},
                    "manual": {},
                }
                requested_profile = body.get("profile")
                if isinstance(requested_profile, str) and requested_profile in PROFILES:
                    stored["profile"] = requested_profile
                manual = dict(stored.get("manual", {}))
                for item_id in item_ids:
                    existing = manual.get(item_id, {})
                    # 일괄 처리 시에도 기존 메모는 보존한다
                    manual[item_id] = {"status": status, "memo": existing.get("memo", "")}
                stored["manual"] = manual
                store.save_checklist_review(identity, stored)
                self._send_json(
                    {
                        "identity": identity,
                        "updated": len(item_ids),
                        "review": compute_review(
                            stored["profile"], stored.get("auto"), manual, stored.get("auto_override")
                        ),
                    }
                )
                return
            if self.path == "/api/checklist/manual":
                body = self._read_json_body()
                identity = str(body.get("identity", "")).strip()
                item_id = str(body.get("item_id", "")).strip()
                status = str(body.get("status", "")).strip()
                memo = str(body.get("memo", ""))
                if not identity or not item_id:
                    self._send_json({"error": "identity와 item_id가 필요합니다."}, status=400)
                    return
                if item_id not in ITEM_IDS:
                    self._send_json({"error": f"알 수 없는 체크 항목: {item_id}"}, status=400)
                    return
                if status not in MANUAL_STATUSES:
                    self._send_json({"error": f"지원하지 않는 체크 상태: {status}"}, status=400)
                    return
                store = _store(config_path)
                stored = store.get_checklist_review(identity) or {
                    "profile": "building",
                    "auto": {},
                    "manual": {},
                }
                requested_profile = body.get("profile")
                if isinstance(requested_profile, str) and requested_profile in PROFILES:
                    stored["profile"] = requested_profile
                manual = dict(stored.get("manual", {}))
                manual[item_id] = {"status": status, "memo": memo}
                stored["manual"] = manual
                store.save_checklist_review(identity, stored)
                self._send_json(
                    {
                        "identity": identity,
                        "review": compute_review(
                            stored["profile"], stored.get("auto"), manual, stored.get("auto_override")
                        ),
                    }
                )
                return
            if self.path == "/api/checklist/auto-override":
                self._handle_auto_override(config_path)
                return
            if self.path == "/api/checklist/suggest":
                self._handle_checklist_suggest()
                return
            if self.path == "/api/report":
                self._handle_report(config_path)
                return
            self.send_error(404, "Not found")

        def end_headers(self) -> None:
            # 로컬 대시보드는 항상 최신 정적 파일을 쓰도록 캐시를 끈다.
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def log_message(self, format: str, *args) -> None:
            return

        def _handle_auto_override(self, config_path: Path) -> None:
            """공공 API가 못 채운 auto·info 항목을 제공 자료 근거로 수동 입력(저장)한다.

            body: {identity, profile?, overrides:[{item_id, status, evidence}]}
            status가 빈 문자열이면 해당 항목의 수동 입력을 제거(자동값으로 복귀)한다.
            """
            body = self._read_json_body()
            identity = str(body.get("identity", "")).strip()
            overrides = body.get("overrides")
            if not identity or not isinstance(overrides, list):
                self._send_json({"error": "identity와 overrides(목록)가 필요합니다."}, status=400)
                return
            cleaned: list[tuple[str, str, str]] = []
            for entry in overrides:
                if not isinstance(entry, dict):
                    self._send_json({"error": "각 override는 객체여야 합니다."}, status=400)
                    return
                item_id = str(entry.get("item_id", "")).strip()
                status = str(entry.get("status", "")).strip()
                evidence = str(entry.get("evidence", ""))
                if item_id not in OVERRIDABLE_ITEM_IDS:
                    self._send_json(
                        {"error": f"수동 입력할 수 없는 항목입니다: {item_id}"}, status=400
                    )
                    return
                if status and status not in AUTO_STATUSES:
                    self._send_json({"error": f"지원하지 않는 상태: {status}"}, status=400)
                    return
                cleaned.append((item_id, status, evidence))

            store = _store(config_path)
            stored = store.get_checklist_review(identity) or {
                "profile": "building",
                "auto": {},
                "manual": {},
                "auto_override": {},
            }
            requested_profile = body.get("profile")
            if isinstance(requested_profile, str) and requested_profile in PROFILES:
                stored["profile"] = requested_profile
            auto_override = dict(stored.get("auto_override", {}))
            for item_id, status, evidence in cleaned:
                if not status:
                    auto_override.pop(item_id, None)  # 빈 상태 = 수동 입력 해제
                else:
                    auto_override[item_id] = {
                        "status": status,
                        "evidence": evidence,
                        "source": "manual",
                        "updated_at": _utc_now_iso(),
                    }
            stored["auto_override"] = auto_override
            store.save_checklist_review(identity, stored)
            self._send_json(
                {
                    "identity": identity,
                    "updated": len(cleaned),
                    "review": compute_review(
                        stored["profile"],
                        stored.get("auto"),
                        stored.get("manual"),
                        auto_override,
                    ),
                }
            )

        def _handle_checklist_suggest(self) -> None:
            """물건 정보(facts)를 매물에 합쳐 자동 판정을 미리 계산한다 (저장 없음).

            수동 입력 페이지에서 '물건 정보로 자동 작성'에 쓴다. 주소가 있으면
            공공 데이터(건축물대장·토지·실거래·심평원 의원/약국)도 시도하고,
            실패한 소스는 errors로 돌려준다.
            body: {listing, profile?, facts?}
            """
            body = self._read_json_body()
            listing = body.get("listing")
            facts = body.get("facts")
            if not isinstance(listing, dict):
                listing = {}
            merged = dict(listing)
            if isinstance(facts, dict):
                # 입력된 값만 덮어쓴다 (None·빈 문자열은 무시)
                for key, value in facts.items():
                    if value is not None and value != "":
                        merged[key] = value
            address = str(merged.get("location", "")).strip()
            if address:
                report = verify_address(address)
                _attach_medical_data(report)
            else:
                report = {"errors": {}}
            auto = evaluate_auto_items(merged, report)
            self._send_json({"auto": auto, "errors": report.get("errors", {})})

        def _handle_report(self, config_path: Path) -> None:
            """매물 하나의 리포트 생성용 종합 데이터 — 공공데이터(건축물대장·토지·실거래·심평원)
            + 체크리스트 판정을 한 번에 돌려준다 (저장 없음). report.html이 이 값으로 렌더한다.

            body: {identity, listing, profile?}
            """
            body = self._read_json_body()
            identity = str(body.get("identity", "")).strip()
            listing = body.get("listing")
            profile = str(body.get("profile", "building"))
            if not isinstance(listing, dict):
                listing = {}
            if profile not in PROFILES:
                profile = "building"
            address = str(listing.get("location", "")).strip()
            if address:
                report = verify_address(address)
                _attach_medical_data(report)
            else:
                report = {"errors": {}}
            auto = evaluate_auto_items(listing, report)
            stored = _store(config_path).get_checklist_review(identity) or {}
            review = compute_review(profile, auto, stored.get("manual"), stored.get("auto_override"))
            self._send_json(
                {
                    "listing": listing,
                    "profile": profile,
                    "parcel": report.get("parcel"),
                    "building": report.get("building"),
                    "land": report.get("land"),
                    "market": report.get("market"),
                    "medical": report.get("medical"),
                    "review": review,
                    "errors": report.get("errors", {}),
                    "generated_at": _utc_now_iso()[:10],
                }
            )

        def _authorized(self) -> bool:
            password = os.environ.get(DASHBOARD_PASSWORD_ENV, "").strip()
            if not password:
                return True
            header = self.headers.get("Authorization", "")
            if not header.startswith("Basic "):
                return False
            try:
                decoded = base64.b64decode(header[6:]).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                return False
            # 아이디는 무엇이든 허용하고 비밀번호만 검사한다
            _, _, provided = decoded.partition(":")
            return hmac.compare_digest(provided, password)

        def _send_unauthorized(self) -> None:
            body = "로그인이 필요합니다. 아이디는 아무거나, 비밀번호를 입력하세요.".encode("utf-8")
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="210 Property Console", charset="UTF-8"')
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return {}
            if length <= 0 or length > MAX_BODY_BYTES:
                return {}
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {}
            return data if isinstance(data, dict) else {}

        def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return RealEstateAlertHandler


def serve(config_path: Path, web_root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = create_handler(config_path=config_path, web_root=web_root)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving dashboard at http://{host}:{port}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def build_detail_payload(store, identity, cs_no, cort_ofc_cd, gds_seq, photo_dir, fetcher=None):
    from realestate_alert.court_auction_detail import fetch_detail, parse_detail
    from realestate_alert.photos import save_photos
    from dataclasses import asdict
    cached = store.get_detail(identity)
    if cached:
        return cached
    payload = fetch_detail(cs_no, cort_ofc_cd, gds_seq, fetcher=fetcher)
    pics = (((payload.get("data") or {}).get("dma_result") or {}).get("csPicLst")) or []
    photo_paths = save_photos(pics, identity, photo_dir)
    detail = parse_detail(payload, identity, photo_paths)
    data = asdict(detail)
    store.upsert_detail(identity, data)
    return data


def safe_photo_path(base: Path, rel: str) -> Path | None:
    if not rel or rel.startswith("/") or ".." in rel.replace("\\", "/").split("/"):
        return None
    candidate = (base / rel).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def _photo_dir(config_path: Path) -> Path:
    cfg = load_config(config_path)
    d = cfg.database_path.parent / "photos"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _store(config_path: Path) -> ListingStore:
    return ListingStore(load_config(config_path).database_path)


def _utc_now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _attach_medical_data(report: dict[str, Any]) -> None:
    """검증 리포트에 같은 동의 정형외과 의원·약국 현황을 덧붙인다 (실패 시 errors에 기록)."""
    parcel = report.get("parcel") or {}
    dong = str(parcel.get("dong") or "").strip()
    if not dong:
        # 법정동코드 미등록 지역은 parcel 파싱이 실패하지만, 심평원 조회는 동 이름만
        # 있으면 되므로 주소 문자열에서 동을 직접 추출해 시도한다.
        dong = extract_dong(str(report.get("address") or "")) or ""
    if not dong:
        return
    try:
        report["medical"] = medical_to_dict(fetch_medical_nearby(dong))
    except PublicDataError as error:
        report.setdefault("errors", {})["medical"] = str(error)


def _review_summaries(config_path: Path) -> dict[str, Any]:
    """저장된 검토 전체를 매물장 배지용 요약(등급·점수·진행률)으로 변환한다."""
    summaries: dict[str, Any] = {}
    for identity, stored in _store(config_path).all_checklist_reviews().items():
        computed = compute_review(
            stored.get("profile", "building"),
            stored.get("auto"),
            stored.get("manual"),
            stored.get("auto_override"),
        )
        summaries[identity] = {
            "profile": computed["profile"],
            "grade": computed["grade"],
            "score": computed["score"],
            "no_go": computed["no_go"],
            "progress": computed["progress"],
            "evaluated_at": stored.get("evaluated_at"),
        }
    return summaries


def _safe_geocode(location: str) -> tuple[float, float] | None:
    try:
        return geocode_parcel(location)
    except PublicDataError:
        return None


def _diagnostics_payload(config_path: Path) -> dict[str, Any]:
    """공공 API 키 설정 여부와 소스별 수집 현황을 보여준다 (키 값 자체는 노출하지 않음).

    클라우드에서 '검색이 안 된다'는 대부분 환경변수 미설정이라, 화면에서 바로
    확인할 수 있도록 키 존재 여부(bool)와 마지막 수집 결과를 반환한다.
    """
    snapshot = _cached_snapshot(config_path)
    source_counts: dict[str, int] = {}
    for listing in snapshot.fetched:
        source_counts[listing.source] = source_counts.get(listing.source, 0) + 1
    fetched_at = _snapshot_fetched_at.get(str(config_path))
    return {
        "keys": {
            "DATA_GO_KR_API_KEY": bool(os.environ.get("DATA_GO_KR_API_KEY", "").strip()),
            "VWORLD_API_KEY": bool(os.environ.get("VWORLD_API_KEY", "").strip()),
        },
        "fetched_count": snapshot.fetched_count,
        "matched_count": snapshot.matched_count,
        "source_counts": source_counts,
        "collecting": str(config_path) in _collecting,
        "has_snapshot": fetched_at is not None,
        "progress": _collect_progress.get(str(config_path)),
        "collected_at": _snapshot_collected_at.get(str(config_path)),
    }


def _listings_payload(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    snapshot = _cached_snapshot(config_path)
    store = ListingStore(config.database_path)
    first_seen = store.first_seen_map()
    favorites = store.favorite_identities()
    details = store.get_all_details()

    def to_dict(listing: Listing, is_match: bool) -> dict[str, Any]:
        detail = details.get(listing.identity) if listing.source == "court" else None
        return _listing_to_dict(
            listing,
            is_new=store.is_recent(first_seen.get(listing.identity)),
            is_favorite=listing.identity in favorites,
            is_match=is_match,
            first_seen_at=first_seen.get(listing.identity),
            # 수집량이 수백 건이라 조건 일치 매물만 좌표 변환한다 (나머지는 선택 시 /api/geocode)
            with_coords=is_match,
            detail=detail,
        )

    matched_ids = {listing.identity for listing in snapshot.matched}
    listings = [to_dict(listing, True) for listing in snapshot.matched]
    unmatched = [
        to_dict(listing, False)
        for listing in snapshot.fetched
        if listing.identity not in matched_ids
    ]
    # 진행 상황(단계)으로 수집 중 여부를 판단한다 — 끝난 소스를 먼저 보여줘도(부분 결과)
    # 좌표 변환까지 끝(phase="done")나야 완료로 표시한다.
    progress = _collect_progress.get(str(config_path))
    collecting = bool(progress and progress.get("phase") != "done")
    return {
        "fetched_count": snapshot.fetched_count,
        "matched_count": snapshot.matched_count,
        "new_count": sum(1 for item in listings if item["is_new"]),
        "favorite_count": len(favorites),
        "listings": listings,
        "unmatched_listings": unmatched,
        # 수집이 진행 중이면 true — UI가 잠시 후 다시 불러오도록 안내
        "collecting": collecting,
        # 수집 진행 상황 — 대시보드가 "수집 갯수 올라가는" 연출에 사용
        "progress": progress,
        # 마지막 수집 완료 시각(UTC ISO) — "마지막 수집 14:32" 표시용
        "collected_at": _snapshot_collected_at.get(str(config_path)),
    }


def _card_extras(listing: Listing, detail: dict[str, Any] | None = None) -> dict[str, Any]:
    """카드 UI 추가 필드. court 물건은 저장된 상세(AuctionDetail)에서 도출."""
    thumbnail_url = None
    photo_count = listing.photo_count
    tags = list(listing.incumbrance_tags)
    if listing.source == "court" and detail:
        photos = detail.get("photos") or []
        if photos:
            thumbnail_url = f"/api/photo?path={quote(photos[0]['file'])}"
        photo_count = len(photos)
        from realestate_alert.court_auction_detail import extract_incumbrance_tags
        tags = list(extract_incumbrance_tags(" ".join(detail.get("incumbrances") or [])))
    elif listing.thumbnail_path:
        thumbnail_url = f"/api/photo?path={quote(listing.thumbnail_path)}"
    detail_link = (
        {
            "id": listing.identity,
            "cs": listing.cs_no,
            "court": listing.cort_ofc_cd,
            "seq": listing.gds_seq,
        }
        if listing.source == "court" and listing.cs_no
        else None
    )
    return {
        "thumbnail_url": thumbnail_url,
        "photo_count": photo_count,
        "incumbrance_tags": tags,
        "detail_link": detail_link,
    }


def _listing_to_dict(
    listing: Listing,
    is_new: bool = False,
    is_favorite: bool = False,
    is_match: bool = True,
    first_seen_at: str | None = None,
    with_coords: bool = True,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # HTTP 응답 경로에서는 절대 동기 지오코딩하지 않는다 — 캐시된 좌표만 읽는다(없으면 None).
    # 좌표 워밍은 백그라운드 수집(_warm_match_coords)이 담당한다.
    coords = cached_coords(listing.location) if with_coords else None
    return {
        "identity": listing.identity,
        "source": listing.source,
        "external_id": listing.external_id,
        "hospital_fit": classify_hospital_fit(listing),
        "usage": listing.usage,
        "title": listing.title,
        "location": listing.location,
        "deposit": listing.deposit,
        "monthly_rent": listing.monthly_rent,
        "appraisal_price": listing.appraisal_price,
        "min_bid_price": listing.min_bid_price,
        "fail_count": listing.fail_count,
        "sale_date": listing.sale_date,
        "area_m2": listing.area_m2,
        "floor": listing.floor,
        "premium": listing.premium,
        "url": listing.url,
        "property_type": listing.property_type,
        "land_area_m2": listing.land_area_m2,
        "building_area_m2": listing.building_area_m2,
        "floors_total": listing.floors_total,
        "parking_spaces": listing.parking_spaces,
        "zoning": listing.zoning,
        "road_access": listing.road_access,
        "building_coverage_ratio": listing.building_coverage_ratio,
        "floor_area_ratio": listing.floor_area_ratio,
        "approval_year": listing.approval_year,
        "elevator": listing.elevator,
        "buildable_note": listing.buildable_note,
        "latitude": coords[0] if coords else None,
        "longitude": coords[1] if coords else None,
        "naver_land_url": (
            naver_land_coord_url(coords[0], coords[1]) if coords else naver_land_url(listing.location)
        ),
        "naver_map_url": naver_map_url(listing.location),
        "is_new": is_new,
        "is_favorite": is_favorite,
        "is_match": is_match,
        "first_seen_at": first_seen_at,
        "registry_status": RegistryStatus.NEEDS_CHECK.value,
        "registry_risks": [],
        "registryText": "",
        **_card_extras(listing, detail),
    }
