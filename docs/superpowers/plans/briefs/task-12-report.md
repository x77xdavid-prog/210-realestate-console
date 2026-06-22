# Task 12 Report — 경매 물건 상세 모달

## Click Handler Hook (web/app.js)

**Location:** lines 1005-1020 (after the `[data-action]` button listener in `renderBoard`).

The existing handler finds the listing by identity and calls `handleCardAction("map", listing)`. The change adds a guard before that call:

```js
if (listing.detail_link) {
  openCourtDetail(listing.detail_link);
  return;
}
handleCardAction("map", listing);   // existing behavior preserved
```

Non-court listings (no `detail_link`) continue to open the map panel unchanged.

## openCourtDetail Function

**Location:** appended near end of app.js before the `/* ===== Boot ===== */` block.

Key details:
- Fetches `/api/listing/detail?id=…&cs=…&court=…&seq=…` via the existing `apiJson` helper.
- Creates/reuses `<div id="cdtScrim" class="cdt-scrim">` appended to `document.body` (lazy, once).
- Renders loading state first, then replaces with full modal HTML on successful fetch.
- Shows an error message inside the modal on fetch failure.
- Sections rendered: header (court/dept/case_no/auction_type + addr_road), gallery, 기본내역, 권리분석 (red box), 기일내역 (timeline), 현황정보.
- Helper functions added: `cdtPyeong(m2)`, `cdtWon(n)` (억/만 formatter), `cdtFmtDate(yyyymmdd)`.
- Reuses existing `apiJson`, `escapeHtml` from app.js.
- `cdtPick(i)` swaps the gallery main image using `data-file` attribute on thumbnails (avoids fragile URL parsing).
- `closeCdtDetail()` removes `.cdt-show` and restores body scroll.
- Backdrop click (click on `.cdt-scrim` itself) also closes.

## CSS Classes Added (web/styles.css)

All prefixed `cdt-` to prevent collision with existing dashboard styles:

| Class | Purpose |
|---|---|
| `.cdt-scrim` / `.cdt-show` | Fixed overlay, shown when active |
| `.cdt-modal` | Centered white card, max-width 1080px |
| `.cdt-loading` | Loading placeholder |
| `.cdt-mhd` | Sticky header with close button |
| `.cdt-ct` / `.cdt-addr` | Header subtitle and address |
| `.cdt-x` | Close button |
| `.cdt-mbody` | Scrollable body padding |
| `.cdt-two` | Two-column grid (1.3fr 1fr), collapses at 820px |
| `.cdt-gal` / `.cdt-gmain` / `.cdt-gthumbs` | Gallery with 4:3 main + thumb strip |
| `.cdt-ton` | Active thumbnail state |
| `.cdt-panel` / `.cdt-bar` | White card panel with accent bar |
| `.cdt-binfo` / `.cdt-bk` / `.cdt-bv` | 2-col key/value grid for 기본내역 |
| `.cdt-risk-box` | Red-tinted panel for 권리분석 |
| `.cdt-note` | Small muted footnote text |
| `.cdt-tl` / `.cdt-tlrow` / `.cdt-tldate` / `.cdt-tlprice` / `.cdt-tlres` | Timeline row layout |
| `.cdt-ry` / `.cdt-rgo` / `.cdt-rdc` / `.cdt-rch` | Result chips: 유찰/진행/매각결정/변경 |
| `.cdt-hyun` / `.cdt-hrow` / `.cdt-hl` / `.cdt-ht` | 현황정보 rows |

Color tokens used: `--rose`, `--rose-soft`, `--teal`, `--green`, `--green-soft`, `--ink`, `--ink-soft`, `--ink-faint`, `--line`, `--shadow-float` — all from existing `:root`.

## Existing Click Behavior Preserved

The guard `if (listing.detail_link) { … return; }` short-circuits only when `detail_link` is truthy. All other listings fall through to the original `handleCardAction("map", listing)` call.

## Scope

Only the 5 sections from `/api/listing/detail` are implemented. No 실거래/심평원/병원적합 panels were added (deferred to a later task).

## Verification

`node --check web/app.js` → exit 0 (no syntax errors).

## Commit Hash

See git log for `feat: 경매 물건 상세 모달(사진·기본내역·권리·기일·현황)`.
