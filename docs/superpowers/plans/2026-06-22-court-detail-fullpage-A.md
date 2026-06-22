# 경매 전용 상세 페이지 — A단계 Implementation Plan

> 실행: superpowers:subagent-driven-development. 체크박스(`- [ ]`) 추적.
> spec: [2026-06-22-court-detail-fullpage-design.md](../specs/2026-06-22-court-detail-fullpage-design.md)

**Goal:** 모달 대신 **새 탭 전용 상세 페이지**를 만들어, 이미 받아오는 데이터 전부(제시외·토지지구·건물상세·현황10·매각공고) + 시세(market_price) + 대법원 문서 링크 + **§1 병원 기능 재사용(적합성·심평원 주변 병원약국·공공데이터 검증·매입계산)**을 담는다. → madangs 구조·깊이 ~75% + 병원분석으로 초월.

**Architecture:** `realestate_alert` 제자리 확장. `parse_detail`가 응답의 미사용 리스트(gdsNotSugtBldLsstAll/rgltLandLstAll/bldSdtrDtlLstAll/gdsRletStLtnoLstAll/dstrtDemnInfo)와 현황 전체를 파싱하도록 확장. 신규 `web/detail.html`+`web/detail.js`가 `/api/listing/detail`(확장)·기존 `/api/verify`·심평원·`market_price`를 호출해 풀페이지 렌더. 보드/모달에 "전체보기 →"로 새 탭 연결.

## Global Constraints
- 외부 호출 실패 흡수, fetcher 주입 테스트(unittest), `AuctionDetail` frozen, 커밋 `<type>: <desc>` (attribution 줄 없음).
- 작업 브랜치: `feat/detail-fullpage` (Task A0에서 생성). 데이터 없는 섹션은 렌더에서 자동 숨김.
- A-리스트 필드명은 **실데이터로 확인**(샘플 2024타경58264은 해당 리스트가 빈 placeholder).

---

## Task A0: 채워진 상세 샘플 캡처 + 필드명 확정 (discovery)
**Files:** Create `samples/court-detail-populated.sample.json`, `docs/superpowers/plans/briefs/A0-fields.md`
- [ ] 브랜치 `feat/detail-fullpage` 생성.
- [ ] **제시외/토지규제/건물상세가 채워진** 물건을 찾는다(단독주택/대지). 방법: `CourtAuctionSource(court_name="서울남부지방법원", target_districts=("강서구",)).fetch()`로 목록을 받아 용도가 "단독주택"/"대지"인 항목의 `cs_no/cort_ofc_cd/gds_seq`를 얻고, `court_auction_detail.fetch_detail(...)`로 상세를 받는다(헤더 fix로 동작 확인됨). `gdsNotSugtBldLsstAll`/`rgltLandLstAll`/`bldSdtrDtlLstAll`/`gdsRletStLtnoLstAll`가 **비어있지 않은** 케이스를 고른다.
- [ ] 그 응답을 base64(picFile) 제거 후 `samples/court-detail-populated.sample.json`로 저장.
- [ ] 각 리스트의 **필드명 + 의미**를 `A0-fields.md`에 기록(예: 제시외 구조/면적/감정가 필드, 토지규제 지역지구코드/명, 건물상세 사용승인일/층수/건축면적).
- [ ] 커밋 `chore: 채워진 경매 상세 샘플 + 필드 매핑`.

## Task A1: 모델 + parse_detail 확장
**Files:** Modify `realestate_alert/models.py`, `realestate_alert/court_auction_detail.py`; Test `tests/test_court_auction_detail.py`
- [ ] `AuctionDetail`에 추가(frozen, 기본 빈 튜플): `presented_outside`(제시외: 용도·구조·면적·감정가), `land_regulations`(지역지구 명 목록), `building_detail`(사용승인일·층수·건축면적), `jibun_list`, `dividend_deadline`, `sale_notice`(물건비고). 값객체는 작은 frozen dataclass 또는 dict 튜플.
- [ ] `parse_detail`: A0에서 확정한 필드명으로 위 리스트들을 파싱. 현황은 **10요항 전부**(이미 STATUS_ORDER 사용 — 유지). 빈 리스트는 빈 튜플.
- [ ] 테스트: `A0` 샘플(또는 인라인 픽스처)로 제시외/토지규제/건물상세 파싱 검증. RED→GREEN.
- [ ] 커밋 `feat: 상세 파서에 제시외·토지지구·건물상세·매각공고 추가`.

## Task A2: 전용 상세 페이지 셸 + A 섹션 렌더
**Files:** Create `web/detail.html`, `web/detail.js`; Modify `web/styles.css`(또는 detail 전용 css)
- [ ] `web/detail.html`: 좌측 sticky 탭(기본내역·현황정보·임차인·등기·시세분석·기타 — 임차인/등기는 B에서 채움, 지금은 placeholder 또는 숨김), 상단 기본내역 바 + 사진 갤러리 + 지도, 우측 레일(대법원 문서 링크: 매각물건명세서·감정평가서·등기부등본·건축물대장 → courtauction URL).
- [ ] `web/detail.js`: URL 쿼리(`id,cs,court,seq`)로 `/api/listing/detail` 호출 → 기본내역·사진·기일·가격(하락률)·**현황10·제시외·토지지구·건물상세·매각공고** 렌더. 데이터 없는 섹션 자동 숨김. `escapeHtml`·`won`·`pyeong` 재사용(모달 로직 공유 가능하면 공유 모듈로).
- [ ] 디자인: 기존 대시보드 톤(자체 스타일에 콘텐츠 주입). madangs형 좌탭/우레일 레이아웃.
- [ ] 라이브 검증: A0 케이스로 새 탭 페이지 렌더 확인(제시외/토지지구/건물상세 표시).
- [ ] 커밋 `feat: 경매 전용 상세 페이지(새 탭) + A 섹션 렌더`.

## Task A3: §1 병원 기능 재사용 (초월 카드)
**Files:** Modify `web/detail.js`(+ html 섹션)
- [ ] 페이지에 병원 분석 섹션 추가, 기존 엔드포인트 연결:
  - **주변 병원·약국**(심평원) — §1에서 쓰던 호출 재사용.
  - **공공데이터 검증**(건축물대장/토지) — `/api/verify` 재사용.
  - **병원 적합성 등급/체크리스트** — `hospital_fit`/checklist 결과 표시.
  - **시세분석** — `market_price`(국토부 실거래) 표시.
  - **매입 계산** — `finance` 진입 버튼/요약.
- [ ] 라이브 검증.
- [ ] 커밋 `feat: 상세 페이지에 병원 분석(심평원·검증·적합성·시세·매입계산) 재사용`.

## Task A4: 보드/모달 → 새 탭 연결
**Files:** Modify `web/app.js`
- [ ] 카드(또는 모달)에 "전체보기 →" 추가: court 물건이면 `window.open('/detail.html?id=&cs=&court=&seq=', '_blank')`. 기존 모달은 빠른 미리보기로 유지.
- [ ] `node --check web/app.js` 통과. 라이브 검증(카드→새 탭).
- [ ] 커밋 `feat: 카드/모달에서 전용 상세 페이지 새 탭 열기`.

## Task A5: 통합·회귀·배포
- [ ] 전체 테스트 `python -m unittest discover -s tests` (UTF-8) — 통과.
- [ ] 라이브 스모크: 데이터 있는 단독주택 케이스로 풀페이지 전 섹션 확인.
- [ ] 기존 모달/보드/캘린더 회귀 없음.
- [ ] main 머지 + 푸시(배포) 또는 PR (사용자 확인).

## Self-Review
- A0가 필드명을 확정하므로 A1 파서가 정확. 데이터 없는 섹션 숨김으로 빈 케이스도 안전.
- B(임차인/당사자)·C(주변입주/청약홈)는 **별도 plan**(이 A 출시 후). 임차인 탭은 A2에서 placeholder.
