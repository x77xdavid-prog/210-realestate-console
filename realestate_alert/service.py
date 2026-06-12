from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from realestate_alert.config import AppConfig, NotifierConfig, SourceConfig
from realestate_alert.filtering import matches_listing
from realestate_alert.models import Listing
from realestate_alert.notifiers import ConsoleNotifier, GmailNotifier, MemoryNotifier, Notifier
from realestate_alert.court_auction import CourtAuctionSource
from realestate_alert.lh_supply import LhNoticeSource
from realestate_alert.onbid import OnbidSource
from realestate_alert.sources import JsonFileSource, ListingSource
from realestate_alert.store import ListingStore


@dataclass(frozen=True)
class RunResult:
    fetched_count: int
    matched_count: int
    notified: list[Listing]


@dataclass(frozen=True)
class ListingSnapshot:
    fetched: list[Listing]
    matched: list[Listing]

    @property
    def fetched_count(self) -> int:
        return len(self.fetched)

    @property
    def matched_count(self) -> int:
        return len(self.matched)


def collect_listings(config: AppConfig) -> ListingSnapshot:
    sources = [_build_source(source_config) for source_config in config.sources]
    fetched: list[Listing] = []
    # 소스가 여러 개라 병렬로 수집한다 (한 소스 실패는 건너뛰고 나머지 진행)
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(sources)))) as pool:
        for result in pool.map(_safe_fetch, sources):
            fetched.extend(result)
    matched = [listing for listing in fetched if matches_listing(config.criteria, listing)]
    return ListingSnapshot(fetched=fetched, matched=matched)


def _safe_fetch(source: ListingSource) -> list[Listing]:
    try:
        return source.fetch()
    except Exception as error:  # noqa: BLE001 — 외부 소스 하나가 죽어도 전체 수집은 계속
        print(f"[collect] 소스 수집 실패 ({type(source).__name__}): {error}")
        return []


def run_once(config: AppConfig) -> RunResult:
    store = ListingStore(config.database_path)
    store.initialize()
    notifiers = [_build_notifier(notifier_config) for notifier_config in config.notifiers]

    snapshot = collect_listings(config)
    new_listings = [listing for listing in snapshot.matched if store.mark_seen_if_new(listing)]

    for notifier in notifiers:
        notifier.notify(new_listings)

    return RunResult(
        fetched_count=snapshot.fetched_count,
        matched_count=snapshot.matched_count,
        notified=new_listings,
    )


def _build_source(config: SourceConfig) -> ListingSource:
    if config.type == "json_file":
        if config.path is None:
            raise ValueError("json_file source requires path.")
        return JsonFileSource(config.path)
    if config.type == "onbid":
        return OnbidSource(
            sido=config.sido or "서울특별시",
            sigungu=config.sigungu or "양천구",
        )
    if config.type == "lh":
        return LhNoticeSource(sido=config.sido or "서울특별시")
    if config.type == "court":
        kwargs: dict = {}
        if config.court:
            kwargs["court_name"] = config.court
        if config.districts:
            kwargs["target_districts"] = config.districts
        return CourtAuctionSource(**kwargs)
    raise ValueError(f"Unsupported source type: {config.type}")


def _build_notifier(config: NotifierConfig) -> Notifier:
    if config.type == "console":
        return ConsoleNotifier()
    if config.type == "memory":
        return MemoryNotifier()
    if config.type == "gmail":
        if not config.sender or not config.recipients:
            raise ValueError("gmail notifier requires sender and recipients.")
        return GmailNotifier(
            sender=config.sender,
            recipients=list(config.recipients),
            password_env=config.password_env or "GMAIL_APP_PASSWORD",
        )
    raise ValueError(f"Unsupported notifier type: {config.type}")
