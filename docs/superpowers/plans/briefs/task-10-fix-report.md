# Task 10 Fix Report — 보드 카드 extras를 저장된 상세에서 도출

## Files Changed

- `realestate_alert/web_server.py`
  - `_card_extras` (line ~1008): added optional `detail: dict[str, Any] | None = None` param; court + detail path derives `thumbnail_url` from `photos[0]['file']`, `photo_count` from `len(photos)`, `tags` via `extract_incumbrance_tags(" ".join(incumbrances))`.
  - `_listing_to_dict` (line ~1031): added `detail: dict[str, Any] | None = None` param; threads it to `_card_extras(listing, detail)`.
  - `_listings_payload` / inner `to_dict` (line ~970): fetches `detail = store.get_detail(listing.identity) if listing.source == "court" else None` per listing; passes it to `_listing_to_dict`.

- `tests/test_web_server.py`
  - `CardExtrasTests`: replaced old listing-attribute-based court tests with new contract tests using `detail` dict. Added `_COURT_DETAIL` fixture. 8 tests total (up from 6).

## Test Output (tail)

```
test_court_with_detail_has_detail_link ... ok
test_court_with_detail_has_photo_count ... ok
test_court_with_detail_has_thumbnail_url ... ok
test_court_with_detail_incumbrance_tags_from_text ... ok
test_court_without_detail_still_has_detail_link ... ok
test_court_without_detail_thumbnail_url_is_none ... ok
test_non_court_listing_detail_link_is_none ... ok
test_non_court_listing_thumbnail_url_is_none ... ok

Ran 8 tests in 0.001s  OK

Full suite: Ran 190 tests in 13.755s  FAILED (errors=1)
```

The single error (`test_deadline_drops_slow_source_and_returns_completed`) is the pre-existing `UnicodeEncodeError: 'cp949' codec can't encode '—'` in `service.py` print statement — unrelated to this change.

## Commit Hash

(see git log)

## Concerns

Per-listing `store.get_detail()` is called for every court listing on every `/api/listings` request. This is acceptable at current scale (typically <50 court listings per fetch), but could be batched with a `get_details_bulk(identities)` method if the store grows large.
