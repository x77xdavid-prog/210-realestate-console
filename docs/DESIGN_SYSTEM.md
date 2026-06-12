# Design System: 부동산 매물 자동검색 대시보드

## Reference
Design direction references `nextlevelbuilder/ui-ux-pro-max-skill`:
- Dashboard style: Data-Dense Dashboard
- Product categories: Healthcare, Financial Dashboard, Real-Time Monitoring
- Delivery checks: visible focus states, hover states, reduced-motion support, responsive layouts, avoid generic AI purple gradients

## Product Fit
This is an operational console, not a landing page. The UI should prioritize scanning, comparison, and repeated review.

## Layout
- Left sidebar: service identity, section navigation, operating note
- Top bar: page title and primary commands
- Metrics row: fetched, matched, registry queue, risk count
- Main panels: search criteria, priority list, listings table, registry queue, purchase estimate

## Visual Style
- Light mode only for the first version
- Compact panels with 8px radius
- Muted green operational palette with amber risk accents
- No oversized hero section
- No decorative gradients, bokeh, or visual filler

## Accessibility
- Native buttons and inputs
- Visible focus outlines
- Semantic headings and tables
- Text labels for status states, not color alone
- `prefers-reduced-motion` respected

## Responsive Targets
- 390px mobile
- 768px tablet
- 1024px small desktop
- 1440px desktop

## Current Entry Point
Open `web/index.html` in a browser.
