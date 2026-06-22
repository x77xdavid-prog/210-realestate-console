# Task 13 Report — 월별 경매 캘린더

## Where render is hooked

`renderDashboard()` (app.js:839) previously called `renderSchedule()`. Replaced with `renderSchedulePanel()`.

`renderSchedulePanel()` (app.js:1274):
- Shows `schedulePanel` unconditionally
- On first call (or when `calState.data === null`): calls `async renderAuctionCalendar(ym)` which fetches `/api/calendar?ym=YYYYMM`
- On subsequent calls (cached): calls `buildCalendarHtml(calState.data, calState.selDay)` — no network round trip
- Month nav buttons call `renderAuctionCalendar` directly after resetting `calState.selDay = null`

## Court code mapping

Defined as `COURT_NAMES` constant (app.js):
```js
const COURT_NAMES = {
  B000210: "서울중앙", B000211: "서울동부", B000215: "서울서부",
  B000212: "서울남부", B000213: "서울북부"
};
```
Unknown codes fall back to the raw code string.

## Board-filter wiring

Fully wired. Clicking a day cell in `buildCalendarHtml`:
1. Toggles `state.dateFilter` between `YYYYMMDD` and `null`
2. Sets `state.boardFilter = "fetched"` and resets `state.fetchedPage = 1`
3. Updates `[data-board-filter]` active classes
4. Calls `renderBoard()` and scrolls to `#board`

This is the same pattern as the old date chip click handler.

## CSS classes added (web/styles.css)

All namespaced with `cal-` prefix:

| Class | Purpose |
|---|---|
| `.cal-tabs` / `.cal-tab` / `.cal-tab-on` | Tab row (visual only) |
| `.cal-loading` / `.cal-error` | Loading / error states |
| `.cal-wrap` | Two-column grid, stacks below 880px |
| `.cal-main` / `.cal-side` | Left calendar / right court panel |
| `.cal-hd` / `.cal-ym-label` / `.cal-navbtn` | Month header + prev/next buttons |
| `.cal-grid` / `.cal-cah` / `.cal-cell` | 7-col day grid |
| `.cal-sun` / `.cal-sat` | Weekend colors (rose / teal) |
| `.cal-has` / `.cal-sel` / `.cal-today` | Clickable / selected / today states |
| `.cal-dn` / `.cal-cn` | Day number / count within cell |
| `.cal-legend` | Bottom legend |
| `.cal-side-hd` / `.cal-today-tag` | Side panel header |
| `.cal-court-grid` / `.cal-crow` / `.cal-crow-all` | Court rows in 2-col grid |
| `.cal-cnm` / `.cal-ccnt` | Court name / court count |

## Concerns / notes

- `elements.scheduleStrip` (app.js:119) is still defined but the `#scheduleStrip` element no longer exists in index.html — querySelector returns null, which is harmless since nothing reads `elements.scheduleStrip` anywhere.
- The 경매신건 / 매각결과 tabs are rendered as visual-only (no data implementation), matching the spec.
- First-load latency is expected per API docs; the "불러오는 중…" loading state is shown while the server aggregates.
