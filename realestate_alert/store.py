from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path

from realestate_alert.models import Listing

NEW_LISTING_WINDOW_HOURS = 72

LEDGER_STATUSES = ["검토중", "연락 완료", "방문 예정", "협상중", "보류", "계약 검토"]
DEFAULT_LEDGER_STATUS = LEDGER_STATUSES[0]


class ListingStore:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS seen_listings (
                        identity TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        external_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        url TEXT NOT NULL,
                        first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS favorite_listings (
                        identity TEXT PRIMARY KEY,
                        listing_json TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ledger_entries (
                        identity TEXT PRIMARY KEY,
                        listing_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        memo TEXT NOT NULL DEFAULT '',
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS checklist_reviews (
                        identity TEXT PRIMARY KEY,
                        review_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS auction_detail (
                        identity TEXT PRIMARY KEY,
                        detail_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                # 주소→좌표 영속 캐시. 좌표는 불변이라 만료가 없고, 성공한 것만 저장해 두면
                # 워커 재시작(인메모리 캐시 소실)에도 지도 핀이 유지된다.
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS geocode_cache (
                        address TEXT PRIMARY KEY,
                        latitude REAL NOT NULL,
                        longitude REAL NOT NULL,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

    def mark_seen_if_new(self, listing: Listing) -> bool:
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO seen_listings
                        (identity, source, external_id, title, url)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (listing.identity, listing.source, listing.external_id, listing.title, listing.url),
                )
                return cursor.rowcount == 1

    def first_seen_map(self) -> dict[str, str]:
        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT identity, first_seen_at FROM seen_listings").fetchall()
        return {identity: first_seen_at for identity, first_seen_at in rows}

    def is_recent(self, first_seen_at: str | None, now: datetime | None = None) -> bool:
        """seen 기록이 없거나 최근 NEW_LISTING_WINDOW_HOURS 안에 처음 발견되면 신규로 본다."""
        if first_seen_at is None:
            return True
        seen_at = _parse_sqlite_timestamp(first_seen_at)
        if seen_at is None:
            return False
        current = now or datetime.now(timezone.utc)
        return current - seen_at <= timedelta(hours=NEW_LISTING_WINDOW_HOURS)

    # --- 관심매물 ---

    def toggle_favorite(self, identity: str, listing: dict) -> bool:
        """관심매물 상태를 뒤집고 새 상태(True=관심 등록됨)를 반환한다."""
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM favorite_listings WHERE identity = ?", (identity,)
                )
                if cursor.rowcount > 0:
                    return False
                connection.execute(
                    "INSERT INTO favorite_listings (identity, listing_json) VALUES (?, ?)",
                    (identity, json.dumps(listing, ensure_ascii=False)),
                )
                return True

    def favorite_identities(self) -> set[str]:
        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute("SELECT identity FROM favorite_listings").fetchall()
        return {identity for (identity,) in rows}

    def list_favorites(self) -> list[dict]:
        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT identity, listing_json, created_at FROM favorite_listings ORDER BY created_at DESC"
            ).fetchall()
        return [
            {"identity": identity, "listing": json.loads(listing_json), "created_at": created_at}
            for identity, listing_json, created_at in rows
        ]

    # --- 매물장 ---

    def upsert_ledger_entry(
        self,
        identity: str,
        listing: dict,
        status: str = DEFAULT_LEDGER_STATUS,
        memo: str = "",
    ) -> dict:
        if status not in LEDGER_STATUSES:
            raise ValueError(f"지원하지 않는 매물장 상태: {status}")
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO ledger_entries (identity, listing_json, status, memo, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(identity) DO UPDATE SET
                        listing_json = excluded.listing_json,
                        status = excluded.status,
                        memo = excluded.memo,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (identity, json.dumps(listing, ensure_ascii=False), status, memo),
                )
        return {"identity": identity, "listing": listing, "status": status, "memo": memo}

    def list_ledger_entries(self) -> list[dict]:
        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT identity, listing_json, status, memo, updated_at
                FROM ledger_entries
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [
            {
                "identity": identity,
                "listing": json.loads(listing_json),
                "status": status,
                "memo": memo,
                "updated_at": updated_at,
            }
            for identity, listing_json, status, memo, updated_at in rows
        ]

    def delete_ledger_entry(self, identity: str) -> bool:
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                # 매물장에서 빠지면 체크리스트 검토도 의미가 없으므로 함께 삭제한다
                connection.execute(
                    "DELETE FROM checklist_reviews WHERE identity = ?", (identity,)
                )
                cursor = connection.execute(
                    "DELETE FROM ledger_entries WHERE identity = ?", (identity,)
                )
                return cursor.rowcount > 0

    # --- 체크리스트 검토 ---

    def save_checklist_review(self, identity: str, review: dict) -> None:
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO checklist_reviews (identity, review_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(identity) DO UPDATE SET
                        review_json = excluded.review_json,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (identity, json.dumps(review, ensure_ascii=False)),
                )

    def get_checklist_review(self, identity: str) -> dict | None:
        self.initialize()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT review_json FROM checklist_reviews WHERE identity = ?", (identity,)
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def all_checklist_reviews(self) -> dict[str, dict]:
        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT identity, review_json FROM checklist_reviews"
            ).fetchall()
        return {identity: json.loads(review_json) for identity, review_json in rows}

    def delete_checklist_review(self, identity: str) -> bool:
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM checklist_reviews WHERE identity = ?", (identity,)
                )
                return cursor.rowcount > 0

    def upsert_detail(self, identity: str, detail_json: dict) -> None:
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO auction_detail (identity, detail_json, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(identity) DO UPDATE SET
                        detail_json = excluded.detail_json, updated_at = CURRENT_TIMESTAMP
                    """,
                    (identity, json.dumps(detail_json, ensure_ascii=False)),
                )

    def get_detail(self, identity: str) -> dict | None:
        self.initialize()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT detail_json FROM auction_detail WHERE identity = ?", (identity,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def get_all_details(self) -> dict[str, dict]:
        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT identity, detail_json FROM auction_detail"
            ).fetchall()
        return {identity: json.loads(dj) for identity, dj in rows}

    # --- 지오코딩 좌표 캐시(영속) ---

    def save_coords(self, address: str, latitude: float, longitude: float) -> None:
        """주소→좌표를 영속 저장한다(같은 주소는 갱신). 성공 좌표만 저장하므로
        워커 재시작에도 핀이 유지되고, 미저장 주소는 다음 수집 때 다시 시도된다."""
        self.initialize()
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO geocode_cache (address, latitude, longitude, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(address) DO UPDATE SET
                        latitude = excluded.latitude,
                        longitude = excluded.longitude,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (address, latitude, longitude),
                )

    def all_coords(self) -> dict[str, tuple[float, float]]:
        """저장된 모든 주소→좌표. 목록 응답의 좌표를 채우고 인메모리 캐시를 prime할 때 쓴다."""
        self.initialize()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT address, latitude, longitude FROM geocode_cache"
            ).fetchall()
        return {address: (latitude, longitude) for address, latitude, longitude in rows}

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)


def _parse_sqlite_timestamp(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
