from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from realestate_alert.models import Listing


class RegistryStatus(StrEnum):
    NEEDS_CHECK = "등기 확인 필요"
    CHECKED = "확인 완료"
    RISK_FOUND = "위험 권리 있음"


RISK_KEYWORDS = ["근저당권", "압류", "가압류", "전세권", "가처분", "임차권등기", "경매개시결정"]


@dataclass(frozen=True)
class RegistryTarget:
    source: str
    external_id: str
    title: str
    address: str
    url: str
    status: RegistryStatus


@dataclass(frozen=True)
class RegistryRiskResult:
    status: RegistryStatus
    owner_names: list[str]
    risk_keywords: list[str]


def build_registry_target(listing: Listing) -> RegistryTarget:
    return RegistryTarget(
        source=listing.source,
        external_id=listing.external_id,
        title=listing.title,
        address=normalize_address(listing.location),
        url=listing.url,
        status=RegistryStatus.NEEDS_CHECK,
    )


def normalize_address(address: str) -> str:
    return " ".join(address.split())


def export_registry_targets(listings: list[Listing], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    targets = [build_registry_target(listing) for listing in listings]
    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["source", "external_id", "title", "address", "url", "status"],
        )
        writer.writeheader()
        for target in targets:
            writer.writerow(
                {
                    "source": target.source,
                    "external_id": target.external_id,
                    "title": target.title,
                    "address": target.address,
                    "url": target.url,
                    "status": target.status.value,
                }
            )


def detect_registry_risks(text: str) -> RegistryRiskResult:
    risk_keywords = [keyword for keyword in RISK_KEYWORDS if keyword in text]
    owner_names = _extract_owner_names(text)
    status = RegistryStatus.RISK_FOUND if risk_keywords else RegistryStatus.CHECKED
    return RegistryRiskResult(
        status=status,
        owner_names=owner_names,
        risk_keywords=risk_keywords,
    )


def read_registry_text(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix.lower() == ".txt":
        return data.decode("utf-8", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def analyze_registry_file(path: Path) -> RegistryRiskResult:
    return detect_registry_risks(read_registry_text(path))


def _extract_owner_names(text: str) -> list[str]:
    names = re.findall(r"소유자\s+([가-힣A-Za-z0-9·()\s]{2,20})", text)
    return [name.strip().split()[0] for name in names if name.strip()]
