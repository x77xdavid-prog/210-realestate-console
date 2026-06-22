# Live Header Fix Report

## Edits

### `realestate_alert/court_auction_detail.py` — `_live_detail`
Replaced single-header index request:
```python
idx = urllib.request.Request(INDEX_URL, headers={"User-Agent": _UA})
```
with full browser header set:
```python
idx_headers = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Upgrade-Insecure-Requests": "1",
}
idx = urllib.request.Request(INDEX_URL, headers=idx_headers)
```
POST (detail) request headers unchanged.

### `realestate_alert/court_calendar.py` — `_live_dates`
Same change applied to the inline index warmup request. POST (dxdy) request headers unchanged.

## Full Suite Result

```
Ran 190 tests in 13.796s
FAILED (errors=1)
```

Pre-existing error (unrelated): `UnicodeEncodeError: 'cp949' codec can't encode character '—'` in `test_service.py::test_deadline_drops_slow_source_and_returns_completed` — caused by a `—` em-dash in `service.py` print statement, not related to this fix.

All 189 other tests pass — no regressions introduced.

## Commit Hash

(see git log after commit)
