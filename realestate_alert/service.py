from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass
from typing import Callable

from realestate_alert.config import AppConfig, NotifierConfig, SourceConfig
from realestate_alert.filtering import matches_listing
from realestate_alert.models import Listing
from realestate_alert.notifiers import ConsoleNotifier, GmailNotifier, MemoryNotifier, Notifier
from realestate_alert.court_auction import CourtAuctionSource
from realestate_alert.lh_supply import LhNoticeSource
from realestate_alert.onbid import OnbidSource
from realestate_alert.sources import JsonFileSource, ListingSource
from realestate_alert.store import ListingStore

# 병원 개원 적합 용도 키워드 — 법원경매 물건 중 상세 보강 대상 판별
_HOSPITAL_FIT_KEYWORDS = ("근린", "상가", "업무", "의료", "사무", "점포")


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


# 수집 진행 콜백: (지금까지 수집된 매물, 완료 소스 수, 전체 소스 수)
ProgressCallback = Callable[[list[Listing], int, int], None]


def collect_listings(
    config: AppConfig,
    on_progress: ProgressCallback | None = None,
    deadline_seconds: float | None = None,
) -> ListingSnapshot:
    sources = [_build_source(source_config) for source_config in config.sources]
    total = len(sources)
    fetched: list[Listing] = []
    done = 0
    # 소스가 여러 개라 병렬로 수집한다 (한 소스 실패는 건너뛰고 나머지 진행).
    # 완료되는 순서대로 받아 진행률을 콜백으로 알린다(수집 갯수가 올라가는 연출용).
    # deadline_seconds를 주면 느린 소스(예: 법원경매)가 그 시간을 넘길 때
    # 끝난 소스 결과만 쓰고 진행한다 — 한 소스가 전체 수집을 무한정 막지 못하게.
    pool = ThreadPoolExecutor(max_workers=min(6, max(1, total)))
    futures = [pool.submit(_safe_fetch, source) for source in sources]
    try:
        for future in as_completed(futures, timeout=deadline_seconds):
            fetched.extend(future.result())
            done += 1
            if on_progress is not None:
                on_progress(fetched, done, total)
    except FuturesTimeoutError:
        print(f"[collect] 수집 마감({deadline_seconds}s) 초과 — {done}/{total} 소스 완료분만 사용")
    finally:
        # 마감을 넘긴 느린 소스는 기다리지 않고 버린다(다음 주기에 재시도).
        pool.shutdown(wait=False, cancel_futures=True)
    matched = [listing for listing in fetched if matches_listing(config.criteria, listing)]
    return ListingSnapshot(fetched=fetched, matched=matched)


def _safe_fetch(source: ListingSource) -> list[Listing]:
    try:
        return source.fetch()
    except Exception as error:  # noqa: BLE001 — 외부 소스 하나가 죽어도 전체 수집은 계속
        print(f"[collect] 소스 수집 실패 ({type(source).__name__}): {error}")
        return []


def is_court_hospital_candidate(listing: Listing) -> bool:
    """법원경매 물건 중 병원 개원 적합 후보인지 판별한다.

    - source가 "court"이어야 한다.
    - cs_no(사건번호)가 있어야 한다(상세 조회 키).
    - 용도/제목에 병원 개원 가능 키워드(근린/상가/업무/의료/사무/점포)가 포함되어야 한다.
    """
    if listing.source != "court":
        return False
    if not listing.cs_no:
        return False
    combined = f"{listing.usage or ''} {listing.title}"
    return any(kw in combined for kw in _HOSPITAL_FIT_KEYWORDS)


def enrich_candidates(
    listings,
    store,
    photo_dir,
    is_candidate,
    fetcher=None,
    sleep=None,
) -> int:
    """후보(court + 병원 적합)만 상세 보강한다. 이미 캐시된 건 건너뜀. 실패는 흡수.

    Args:
        listings: Listing 목록.
        store: ListingStore 인스턴스.
        photo_dir: 사진 저장 디렉터리(Path).
        is_candidate: (Listing) -> bool 후보 판별 함수.
        fetcher: court_auction_detail.fetch_detail에 주입할 fetcher(테스트용).
        sleep: 호출 간격 조절 함수. 없으면 간격 없음.

    Returns:
        보강에 성공한 건수.
    """
    from realestate_alert.web_server import build_detail_payload
    enriched = 0
    for ls in listings:
        if not is_candidate(ls):
            continue
        if store.get_detail(ls.identity):   # 이미 캐시된 건 건너뜀
            continue
        try:
            build_detail_payload(
                store, ls.identity, ls.cs_no, ls.cort_ofc_cd, ls.gds_seq,
                photo_dir=photo_dir, fetcher=fetcher,
            )
            enriched += 1
            if sleep:
                sleep()
        except Exception:  # noqa: BLE001 — 외부 호출 실패는 흡수, 다음 주기에 재시도
            continue
    return enriched


def run_once(config: AppConfig, snapshot: ListingSnapshot | None = None) -> RunResult:
    store = ListingStore(config.database_path)
    store.initialize()
    notifiers = [_build_notifier(notifier_config) for notifier_config in config.notifiers]

    # 스캔 경로에서 이미 수집한 스냅샷을 재사용해 중복 수집을 피한다(없으면 새로 수집).
    if snapshot is None:
        snapshot = collect_listings(config)
    new_listings = [listing for listing in snapshot.matched if store.mark_seen_if_new(listing)]

    for notifier in notifiers:
        notifier.notify(new_listings)

    # 법원경매 후보 물건만 상세 보강(신규/관심 한정 정책은 enrich_candidates 내부에서 캐시로 처리).
    # 실패해도 알림·결과에 영향 없이 흡수한다.
    try:
        import time as _time
        from pathlib import Path as _Path
        photo_dir = config.database_path.parent / "photos"
        _Path(photo_dir).mkdir(parents=True, exist_ok=True)
        enrich_candidates(
            snapshot.fetched,
            store,
            photo_dir,
            is_candidate=is_court_hospital_candidate,
            sleep=lambda: _time.sleep(1),
        )
    except Exception:  # noqa: BLE001 — 보강 실패는 흡수
        pass

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
