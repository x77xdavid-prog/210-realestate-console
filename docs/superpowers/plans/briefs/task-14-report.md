# Task 14 Implementation Report: 수집 연결 — 후보 상세 보강 + config

## Approach

`build_detail_payload` from `web_server.py` was reused (cache-first builder) rather than inlining the fetch→parse→save sequence. No circular import occurred because the import is deferred inside `enrich_candidates()` (lazy `from realestate_alert.web_server import build_detail_payload`).

## Files Changed

| File | Change |
|---|---|
| `realestate_alert/service.py` | Added `_HOSPITAL_FIT_KEYWORDS` constant, `is_court_hospital_candidate()`, `enrich_candidates()`, and wired call into `run_once()` |
| `tests/test_service.py` | Added `_make_listing()` helper, `IsCourtHospitalCandidateTests` (6 cases), `EnrichCandidatesTests` (4 cases) |
| `config.local.json` | Added `{ "type": "court", "court": "서울남부지방법원", ... }` source |
| `config.example.json` | Already had court source — no change needed |
| `config.render.json` | Already had court source — no change needed |

## Implementation Notes

- `enrich_candidates()` imports `build_detail_payload` lazily to avoid circular import at module level.
- `run_once()` wraps the enrich call in `try/except Exception` so enrichment failure never blocks notification flow.
- `is_court_hospital_candidate()` checks `source == "court"`, `cs_no` truthy, and usage/title contains any of: 근린/상가/업무/의료/사무/점포.
- Sleep interval between enrichment calls is 1 second (injected as lambda).
- The `_make_listing()` test helper uses `usage="근린생활시설"` as default; the apartment test explicitly sets `title="아파트 2층"` to avoid keyword false-positives.

## Test Output (tail)

```
test_failure_is_absorbed_and_continues ... ok
test_fetcher_called_once_for_fresh_court_candidate ... ok
test_fetcher_not_called_for_non_candidate ... ok
test_fetcher_not_called_when_already_cached ... ok
test_court_apartment_returns_false ... ok
test_court_eommu_usage_returns_true ... ok
test_court_sangga_usage_returns_true ... ok
test_court_with_cs_no_and_commercial_usage_returns_true ... ok
test_court_without_cs_no_returns_false ... ok
test_onbid_returns_false ... ok
test_run_once_notifies_only_matching_new_listings ... ok

Ran 188 tests in 13.738s
FAILED (errors=1)  ← pre-existing UnicodeEncodeError only
```

## Commit Hash

(see git log after commit)

## Concerns

- The `run_once()` enrichment sleep (1s per candidate) can make scans noticeably slower when many court candidates appear. Consider moving the enrich step to a background thread in a future task if scan latency becomes an issue.
