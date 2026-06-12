from __future__ import annotations

import base64
import hmac
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from realestate_alert.checklist import (
    ITEM_IDS,
    MANUAL_STATUSES,
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
from realestate_alert.land_info import geocode_parcel
from realestate_alert.medical_nearby import fetch_medical_nearby, medical_to_dict
from realestate_alert.models import Listing
from realestate_alert.naver import naver_land_coord_url, naver_land_url, naver_map_url
from realestate_alert.public_data import PublicDataError
from realestate_alert.registry import RegistryStatus
from realestate_alert.service import collect_listings, run_once
from realestate_alert.store import LEDGER_STATUSES, ListingStore
from realestate_alert.verify import verify_address

MAX_BODY_BYTES = 256 * 1024

# 설정 시 모든 요청에 브라우저 기본 로그인(아이디 무관, 비밀번호 일치)을 요구한다.
# 로컬 전용 사용이면 비워 두면 된다 — 클라우드 공개 배포 시 필수.
DASHBOARD_PASSWORD_ENV = "DASHBOARD_PASSWORD"


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
                    review = compute_review(profile, stored.get("auto"), stored.get("manual"))
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
                result = run_once(load_config(config_path))
                self._send_json(
                    {
                        "fetched_count": result.fetched_count,
                        "matched_count": result.matched_count,
                        "notified_count": len(result.notified),
                        "notified": [_listing_to_dict(listing) for listing in result.notified],
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
                    "evaluated_at": _utc_now_iso(),
                }
                store.save_checklist_review(identity, review)
                self._send_json(
                    {
                        "identity": identity,
                        "review": compute_review(profile, auto, review["manual"]),
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
                            stored["profile"], stored.get("auto"), manual
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
                            stored["profile"], stored.get("auto"), manual
                        ),
                    }
                )
                return
            self.send_error(404, "Not found")

        def end_headers(self) -> None:
            # 로컬 대시보드는 항상 최신 정적 파일을 쓰도록 캐시를 끈다.
            self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def log_message(self, format: str, *args) -> None:
            return

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
            stored.get("profile", "building"), stored.get("auto"), stored.get("manual")
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


def _listings_payload(config_path: Path) -> dict[str, Any]:
    config = load_config(config_path)
    snapshot = collect_listings(config)
    store = ListingStore(config.database_path)
    first_seen = store.first_seen_map()
    favorites = store.favorite_identities()

    def to_dict(listing: Listing, is_match: bool) -> dict[str, Any]:
        return _listing_to_dict(
            listing,
            is_new=store.is_recent(first_seen.get(listing.identity)),
            is_favorite=listing.identity in favorites,
            is_match=is_match,
            first_seen_at=first_seen.get(listing.identity),
        )

    matched_ids = {listing.identity for listing in snapshot.matched}
    listings = [to_dict(listing, True) for listing in snapshot.matched]
    unmatched = [
        to_dict(listing, False)
        for listing in snapshot.fetched
        if listing.identity not in matched_ids
    ]
    return {
        "fetched_count": snapshot.fetched_count,
        "matched_count": snapshot.matched_count,
        "new_count": sum(1 for item in listings if item["is_new"]),
        "favorite_count": len(favorites),
        "listings": listings,
        "unmatched_listings": unmatched,
    }


def _listing_to_dict(
    listing: Listing,
    is_new: bool = False,
    is_favorite: bool = False,
    is_match: bool = True,
    first_seen_at: str | None = None,
) -> dict[str, Any]:
    coords = _safe_geocode(listing.location)
    return {
        "identity": listing.identity,
        "source": listing.source,
        "external_id": listing.external_id,
        "title": listing.title,
        "location": listing.location,
        "deposit": listing.deposit,
        "monthly_rent": listing.monthly_rent,
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
    }
