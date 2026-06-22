# A1 Implementation Report — AuctionDetail Sub-list Fields

## Model Fields Added (`realestate_alert/models.py`)

Five new fields appended to `AuctionDetail` (frozen dataclass, all with safe defaults):

| Field | Type | Description |
|-------|------|-------------|
| `presented_outside` | `tuple[dict, ...]` | 제시외건물 items: `{usage, structure, area, appraisal, note}` |
| `building_detail` | `tuple[dict, ...]` | 건물상세 items: `{kind, detail}` |
| `jibun_list` | `tuple[dict, ...]` | 지번 목록 items: `{jibun, addr, road}` |
| `dividend_deadline` | `str \| None` | 배당요구종기 YYYYMMDD |
| `sale_notice` | `str \| None` | 물건비고 (dspslGdsRmk) |

## Parser Logic (`realestate_alert/court_auction_detail.py`)

Added `_first_list(r, key)` helper: handles the `list[list[dict]]` nesting where `key[0]` holds the items.

- **presented_outside**: iterates `_first_list(r, 'gdsNotSugtBldLsstAll')`, skips all-empty rows
- **building_detail**: iterates `_first_list(r, 'bldSdtrDtlLstAll')`
- **jibun_list**: iterates `_first_list(r, 'gdsRletStLtnoLstAll')`, builds `addr` from si/gun/gu/emd parts, `road` as `rdnm + rdnmBldNo`
- **dividend_deadline**: `(r.get('dstrtDemnInfo') or [{}])[0].get('dstrtDemnLstprdYmd')`
- **sale_notice**: `(r.get('dspslGdsDxdyInfo') or {}).get('dspslGdsRmk')`

All wrapped with defensive `.get` and absorb-exception blocks.

## Test Output

```
test_bid_result_maps ... ok
test_incumbrance_tags_extracted ... ok
test_parse_detail_builds_auction_detail ... ok
test_status_label_maps_code ... ok
test_building_detail_parsed ... ok
test_dividend_deadline_parsed ... ok
test_jibun_list_parsed ... ok
test_presented_outside_parsed ... ok
test_sale_notice_parsed ... ok

Ran 9 tests in 0.002s

OK
```

Full suite: 191 tests, 1 pre-existing error (cp949 em-dash encoding in service.py, unrelated).

## Commit

feat: 상세 파서에 제시외·건물상세·지번·배당종기·물건비고 추가
