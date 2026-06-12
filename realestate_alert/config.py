from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from realestate_alert.models import SearchCriteria


@dataclass(frozen=True)
class SourceConfig:
    type: str
    path: Path | None = None
    sido: str | None = None
    sigungu: str | None = None


@dataclass(frozen=True)
class NotifierConfig:
    type: str
    url: str | None = None
    token: str | None = None
    chat_id: str | None = None
    sender: str | None = None
    recipients: tuple[str, ...] = ()
    password_env: str | None = None


@dataclass(frozen=True)
class AppConfig:
    database_path: Path
    criteria: SearchCriteria
    sources: list[SourceConfig]
    notifiers: list[NotifierConfig]
    interval_seconds: int = 600


def load_config(path: Path) -> AppConfig:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    base_dir = path.parent
    criteria_data = data.get("criteria", {})
    sources_data = data.get("sources", [])
    notifiers_data = data.get("notifiers", [{"type": "console"}])
    if not sources_data:
        raise ValueError("At least one source is required.")

    return AppConfig(
        database_path=_resolve_path(base_dir, data.get("database_path", "data/seen.sqlite3")),
        criteria=SearchCriteria(
            locations=list(criteria_data.get("locations", [])),
            max_deposit=criteria_data.get("max_deposit"),
            max_monthly_rent=criteria_data.get("max_monthly_rent"),
            min_area_m2=criteria_data.get("min_area_m2"),
            max_premium=criteria_data.get("max_premium"),
            required_keywords=list(criteria_data.get("required_keywords", [])),
        ),
        sources=[
            SourceConfig(
                type=str(item["type"]),
                path=_optional_resolved_path(base_dir, item.get("path")),
                sido=item.get("sido"),
                sigungu=item.get("sigungu"),
            )
            for item in sources_data
        ],
        notifiers=[
            NotifierConfig(
                type=str(item["type"]),
                url=item.get("url"),
                token=item.get("token"),
                chat_id=item.get("chat_id"),
                sender=item.get("sender"),
                recipients=tuple(item.get("recipients", [])),
                password_env=item.get("password_env"),
            )
            for item in notifiers_data
        ],
        interval_seconds=int(data.get("interval_seconds", 600)),
    )


def _optional_resolved_path(base_dir: Path, value: str | None) -> Path | None:
    if value is None:
        return None
    return _resolve_path(base_dir, value)


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base_dir / path
