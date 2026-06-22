# A2-report — 경매 전용 상세 페이지 (새 탭)

## Files Created

| Path | Purpose |
|------|---------|
| `web/detail.html` | Full-page shell: header, case-header strip, 3-column body (left rail / main / right rail), lightbox overlay |
| `web/detail.js` | Controller: URL param parsing, `/api/listing/detail` fetch, all render functions, tab nav, lightbox, helpers |
| `web/detail.css` | Scoped styles under `dp-` namespace, mirrors design tokens from `styles.css`, responsive breakpoints |

## Layout Summary

```
┌─────────────────────────── dp-header (sticky 56px) ───────────────────────────┐
│ ← 목록   병원매물 자동검색 · 물건 상세                                            │
├──────────────────────────────────────────────────────────────────────────────────┤
│ dp-case-header: [court badge] [case_no] [auction_type] / addr_road / addr_jibun│
├──────────────────────────────────────────────────────────────────────────────────┤
│ dp-body (CSS grid: 200px | 1fr | 220px)                                         │
│ ┌──────────────┐ ┌──────────────────────────────┐ ┌────────────────────────┐    │
│ │ dp-left-rail │ │ dp-main                       │ │ dp-right-rail          │    │
│ │ (sticky)     │ │                               │ │ (sticky)               │    │
│ │ 기본내역     │ │ • 사진 갤러리 + 지도 panel    │ │ 대법원 문서 links:     │    │
│ │ 현황정보     │ │ • 기본내역 table              │ │ 법원경매정보           │    │
│ │ 제시외/건물  │ │ • 가격·시세 cards             │ │ 매각물건명세서         │    │
│ │ 등기/지번    │ │ • 권리분석 인수사항           │ │ 감정평가서             │    │
│ │ 시세분석     │ │ • 기일내역 table              │ │ 현황조사서             │    │
│ │ 기타         │ │ • 현황정보                    │ │ 등기부등본             │    │
│ └──────────────┘ │ • 제시외건물 (조건부)         │ │ 건축물대장             │    │
│                  │ • 건물상세 (조건부)            │ │                        │    │
│                  │ • 지번목록 (조건부)            │ │ 사건번호 열람 note     │    │
│                  │ • 물건비고 (조건부)            │ └────────────────────────┘    │
│                  └──────────────────────────────┘                               │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Helpers (detail.js)

| Helper | Signature | Description |
|--------|-----------|-------------|
| `escapeHtml(str)` | `(any) → string` | Escapes `& < > " '`; applied to ALL dynamic text |
| `won(n)` | `(number) → string` | 억/만 Korean currency: e.g. `1_050_000_000 → "10억 5,000만"` |
| `pyeong(m2)` | `(number) → string` | `m² + 평` both: e.g. `"123.0m² (37.2평)"` |
| `fmtY(s)` | `(string) → string` | `"YYYYMMDD" → "YYYY.MM.DD"` |
| `dropRate(min, appr)` | `(number, number) → string` | `round((1 - min/appr)*100)` → `"−30%"` |
| `perPyeong(amt, m2)` | `(number, number) → string` | Won per pyeong for price cards |

## Empty-Section Auto-Hide

Sections that conditionally render are handled by individual render functions:

| Section | Condition | Mechanism |
|---------|-----------|-----------|
| `#sec-presented` | `presented_outside.length === 0` AND `building_detail.length === 0` | Both sub-wraps have `hidden`; parent section stays `hidden` unless either sub-wrap has content |
| `#sec-register` | `jibun_list.length === 0` | `sec.hidden = true` before early return |
| `#sec-misc` | `sale_notice` is falsy | `sec.hidden = true` before early return |
| Status items | empty array | Renders "현황정보 없음" placeholder (section always visible) |
| Incumbrances | empty array | Renders "특이 인수사항 없음" in green (section always visible) |
| Bid history | empty array | Renders empty-state row (section always visible) |
| Gallery | `photos.length === 0` | Shows "사진 없음" placeholder instead |
| Map | `latitude`/`longitude` falsy | Shows "위치 정보 없음" placeholder instead |

## How the Page Works

1. `boot()` runs on `DOMContentLoaded`.
2. URL params `?id=&cs=&court=&seq=` are extracted via `URLSearchParams`.
3. If `id` is missing, the error state is shown immediately.
4. `fetchDetail()` calls `GET /api/listing/detail?id=...&cs=...&court=...&seq=...`.
5. On success, `renderAll(data)` dispatches to all individual render functions.
6. The loading spinner hides; `#dp-body` and `#dp-case-header` become visible.
7. On failure, the error state shows with HTTP status or network message.

## Commit Hash

`a629069`

## Concerns / Notes

- Doc links all point to `https://www.courtauction.go.kr` root — per-document deep-links are not available in the API response. The right rail notes "사건번호로 열람" to guide the user.
- The OpenStreetMap iframe uses a small bbox around lat/lng. This works without an API key and is GDPR-friendly, but requires the server to have `latitude`/`longitude` populated in the detail payload.
- `node --check web/detail.js` exits 0 (verified).
- CSS uses `dp-` namespace throughout to avoid collisions with `styles.css` (loaded only in `index.html`); `detail.html` loads `detail.css` independently.
- Responsive: ≤820px collapses to single column; tab nav becomes a horizontal wrap.
