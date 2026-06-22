# §3 공매(온비드) 캘린더 구분·필터 — 설계

작성일: 2026-06-23
관련 메모: 병원매물 진행 상태(§3 로드맵)

## 1. 목표

기존 "월별 경매일정" 캘린더에 **이미 섞여 표시되는** 공매(온비드) 물건을 경매와 **시각적으로 구분**하고, **전체/경매/공매 필터**를 추가한다. 공매 항목에는 입찰기간과 온비드 링크를 노출한다.

확정된 설계 결정(브레인스토밍):
- 핵심: **경매↔공매 구분 + 필터** (공매는 이미 수집·표시되나 구분이 없음).
- 입찰기간: **마감일 기준 유지 + 기간은 텍스트**로 표기(캘린더 그리드는 단순하게, 멀티데이 구간 표시 안 함).
- 범위: 캘린더 한정(보드/추천으로 확장하지 않음).

## 2. 현재 상태

- `onbid.py`(`OnbidSource`)가 공공데이터 온비드 API로 공매 물건을 수집하고 `Listing(source="onbid", sale_date=입찰마감일[:8], appraisal_price, min_bid_price, buildable_note="… 입찰 {begin}~{end} …")`를 만든다. `config.render.json`에 양천/강서/구로/영등포 onbid 소스가 있어 프로덕션에서 수집된다.
- `web/app.js`의 `renderAuctionCalendar`(약 1366줄)가 `[...state.listings, ...state.unmatched]`를 `sale_date`(YYYYMMDD)로 월별 집계한다. 경매(court)와 공매(onbid)가 **구분 없이** 같은 날짜 셀·사이드패널에 섞인다. 사이드패널 항목은 제목+가격만 보이고 소스 배지가 없다.
- `index.html`에 단일 탭 `경매일정`(`cal-tab cal-tab-on`)만 있다.
- 입찰기간 begin~end는 `buildable_note` 텍스트 안에만 있고 구조화 필드가 없다.

## 3. Backend

### 3.1 `models.Listing` — 선택 필드 추가
```python
bid_begin: str | None = None   # 공매 입찰 시작일 YYYYMMDD
bid_end: str | None = None     # 공매 입찰 마감일 YYYYMMDD
```
기존 필드 뒤에 기본값 None으로 추가(모든 기존 생성 호환).

### 3.2 `onbid.py` — 구조화 추출
입찰 시작/마감을 `bid_begin`/`bid_end`(YYYYMMDD)로 채운다. 기존 `note`의 `입찰 {begin}~{end}` 텍스트와 `sale_date=end[:8]`는 유지. begin/end 원문이 8자리 미만이면 해당 필드는 None.

### 3.3 `web_server._listing_to_dict` — 직렬화
응답 dict에 `bid_begin`, `bid_end` 추가. `source`는 이미 내려가므로 프론트가 경매/공매를 구분할 수 있다. **새 엔드포인트 없음** — 캘린더는 기존 `/api/listings` 데이터를 그대로 쓴다.

## 4. Frontend

### 4.1 필터 탭
`index.html`의 캘린더 헤더에 `전체 / 경매 / 공매` 탭 3개(기존 `cal-tab` 스타일). `calState.kind`("all"|"court"|"onbid"), 기본 "all". 탭 클릭 → `renderAuctionCalendar` 재호출.

### 4.2 구분 로직
- `auctionKind(listing)`: `source === "onbid"` → `"onbid"`, `source === "court"` → `"court"`, 그 외 → `"court"`로 취급하지 않고 `"other"`(캘린더는 sale_date 있는 court·onbid 위주라 영향 적음).
- `renderAuctionCalendar(ym)`가 집계 전에 `calState.kind`로 행을 거른다(all이면 court+onbid 모두). 날짜 카운트·사이드패널 모두 필터 반영.

### 4.3 시각 구분
- 사이드패널 항목에 **소스 배지**: 경매(teal)·공매(amber). 
- 공매 항목: "입찰 {fmt(bid_begin)}~{fmt(bid_end)}" 텍스트 + 온비드(onbid.co.kr) 링크(`listing.url`).
- 전체 보기(kind="all")일 때, 공매가 있는 날 셀에 작은 공매 표식(dot). 카운트는 필터 합계.
- 빈 필터: 사이드/그리드에 "해당 유형 일정이 없습니다" 안내.

### 4.4 styles.css
필터 탭 active 상태, 소스 배지 색(경매 teal / 공매 amber), 공매 dot.

## 5. 모듈 경계
`onbid.py`(데이터) → `models.Listing`(필드) → `web_server`(직렬화) → `app.js`(필터·렌더). 순수 추가이며 기존 경매 캘린더 동작을 보존한다.

## 6. 에러 처리
- `bid_begin`/`bid_end` 누락 → 기간 텍스트 생략(graceful).
- 잘못된 날짜 형식 → 무시(기존 `sale_date.length !== 8` 가드 유지).
- 필터 결과 0건 → 안내 문구.

## 7. 테스트 (기존 271 통과 유지)
- `onbid`: 샘플 item dict로 `bid_begin`/`bid_end` 추출(8자리 정상·미달 시 None) 단위 테스트.
- `_listing_to_dict`: `bid_begin`/`bid_end` 직렬화 확인(기존 web_server 테스트 패턴).
- 프론트: 로컬 playwright로 탭 전환(전체/경매/공매)·소스 배지·공매 기간 텍스트 시각 검증.

## 8. 범위 밖(YAGNI)
- 입찰기간 멀티데이 구간 표시.
- 공매 전용 별도 화면.
- 보드(추천/수집전체)로의 공매 필터 확장.
- 개찰일 별도 표기.

## 9. 구현 순서(plan 입력)
1. `models.Listing`에 `bid_begin`/`bid_end` 추가.
2. `onbid.py` 구조화 추출 + 단위 테스트(RED→GREEN).
3. `_listing_to_dict` 직렬화 + 테스트.
4. `app.js` 필터 탭·`auctionKind`·필터 집계·배지·기간 텍스트, `index.html` 탭, `styles.css`.
5. 로컬 라이브 검증(playwright) + opus 코드리뷰.
