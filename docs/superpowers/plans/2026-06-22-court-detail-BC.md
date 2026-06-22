# 경매 전용 상세 페이지 — B·C단계 Implementation Plan

> 실행: TDD + 라이브 검증. 체크박스(`- [ ]`) 추적. 배포본 제자리 확장.
> spec: [2026-06-22-court-detail-fullpage-design.md](../specs/2026-06-22-court-detail-fullpage-design.md)
> 선행: A단계 출시 완료(main 630bef1). B1 역공학 검증 완료 → [briefs/B1-discovery-report.md](briefs/B1-discovery-report.md)
> 사용자 결정(2026-06-22): **전체 순차 C → B-link → B-full**.

**Goal:** madangs caview 90%+/초월. 격차 = 시세·주변통계(C), 임차인/당사자/권리 원문·구조화(B). B1 결과: 임차인/당사자는 **JSON 없음**, 매각물건명세서·현황조사서 **PDF**(ecfs/StreamDocs, 클라이언트 AES `encParam`).

**Global Constraints**
- 외부 호출 실패 흡수, fetcher 주입 테스트(unittest), frozen 모델, 커밋 `<type>: <desc>`(attribution 줄 없음).
- 작업 브랜치: `feat/detail-bc`. 데이터 없는 섹션 자동 숨김. UTF-8 테스트 실행.
- 보안: 비밀키 하드코딩 금지(config/env). 동적 텍스트 escapeHtml.

---

## C단계 — 시세·주변통계 (저비용 고가치, 견고)

### Task C1: 시세분석 탭 강화 (실거래 시세)
**Files:** `realestate_alert/web_server.py`(+`/api/market`), `web/detail.html`, `web/detail.js`; Test `tests/test_web_server.py`
- [ ] 경량 엔드포인트 `POST /api/market {address, months}` → `summarize_market`만 호출(verify의 3중 호출 회피). 키 없음/실패는 `{market:null, error}` 흡수.
- [ ] detail.js: 페이지 로드 후 `addr_jibun`으로 `/api/market` 비동기 호출 → **시세분석 섹션**에 렌더: 평균/최저/최고 ㎡당가, 거래건수, 조회기간, **최근 실거래 테이블**(동·용도·거래가·면적·㎡당가·거래일). market 응답의 min/max/recent_trades 활용(현재 미사용).
- [ ] 데이터 없음/에러 시 안내 문구. 병원분석의 market 그룹은 유지(중복 허용) 또는 참조.
- [ ] 테스트(fetcher 주입): `/api/market`가 summary dict 반환. RED→GREEN.
- [ ] 라이브 검증(상가/업무용 물건). 커밋 `feat: 상세 시세분석 탭에 실거래 시세 직접 표시`.

### Task C2: 주변 매각통계 (자체 수집 데이터 집계)
**Files:** `web/detail.html`, `web/detail.js`(+ 집계 util); 선택 `web_server.py`
- [ ] 신규 섹션 "주변 경매 통계" + 좌측 탭. detail.js가 `/api/listings`(보유) 조회 → 현재 물건과 **같은 시군구/동** 물건 필터.
- [ ] 집계: 인근 경매물건 수, 평균 하락률(`1-min_bid/appraisal`), 용도별 분포, 평균 유찰횟수, 감정가 분포. madangs "주변 매각통계" 대응.
- [ ] 데이터 부족(<N건)은 안내. 클라이언트 집계(서버 부하 0).
- [ ] 라이브 검증. 커밋 `feat: 상세 페이지 주변 경매 통계(자체 데이터 집계)`.

### Task C3: 주변 입주예정 (청약홈/분양 API)
**Files:** Create `realestate_alert/cheongyak.py`; `web_server.py`(+`/api/nearby-supply`), `web/detail.*`; Test `tests/test_cheongyak.py`
- [ ] data.go.kr 청약홈 분양정보 API 조사(활용신청 필요 가능) → `fetch_nearby_supply(sigungu_code/dong)`. 키 없음/실패 흡수.
- [ ] 엔드포인트 + "주변 입주예정" 섹션(단지명·세대수·입주예정·거리). 데이터 없으면 숨김.
- [ ] 테스트(fetcher 주입). 라이브(키 가능 시). 커밋 `feat: 주변 입주예정(청약홈) 연동`.

---

## B-link — 공식 문서 바로가기 (encParam 재현)

### Task BL0: encParam 생성 역공학 (스파이크)
**Files:** `docs/superpowers/plans/briefs/BL0-encparam.md`
- [ ] courtauction JS 번들(`javascriptPluginAll.wq`·페이지 컨트롤러)에서 매각물건명세서/현황조사서 버튼 핸들러 추적 → encParam 생성 함수·AES 키·평문 구조(ecdocId/cortCd/csNo/seq 등) 확정.
- [ ] Python으로 encParam 재현 PoC(보유 `doc_ecid` + identity로). 정적 키면 채택, 동적이면 헤드리스 1회 구동 대안 평가.
- [ ] 기록 + go/no-go.

### Task BL1: 문서 딥링크 엔드포인트 + 우측 레일
**Files:** `realestate_alert/documents.py` 또는 신규 `court_documents.py`; `web_server.py`, `web/detail.js`; Test
- [ ] `build_doc_viewer_url(kind, identity)` → ecfs 뷰어 URL(매각물건명세서·현황조사서·감정평가서). 엔드포인트 `/api/listing/docs?id=`.
- [ ] detail.html 우측 레일의 **placeholder 링크 교체**(현재 전부 맨 courtauction URL) → 실제 문서 딥링크(새 탭). 생성 불가 문서는 courtauction 안내 유지.
- [ ] 테스트(URL 생성). 라이브(클릭→PDF 열림). 커밋 `feat: 상세 우측 레일 공식 문서 딥링크(매각물건명세서·현황조사서·감정평가서)`.

---

## B-full — 임차인·권리 구조화 (PDF 파싱)

### Task BF1: 매각물건명세서 PDF 취득
**Files:** `realestate_alert/court_documents.py`; Test
- [ ] encParam(BL0) → `getPdf.on` → streamdocs `texts/N`(텍스트레이어) 또는 PDF 다운로드. EUC-KR·좌표 처리.
- [ ] fetcher 주입 + 캡처 픽스처로 테스트.

### Task BF2: 임차인·권리 파서
**Files:** `realestate_alert/court_documents.py`, `models.py`; Test
- [ ] 매각물건명세서 텍스트 → 임차인 표(점유자·전입·확정·배당요구·보증금·차임·대항력) + 말소기준/인수권리 파싱. 좌표 기반 행 재구성 또는 pdfplumber.
- [ ] `AuctionDetail`에 `tenants`,`parties`(빈 튜플 기본). 픽스처 테스트(채워진/빈 케이스).

### Task BF3: 임차인/당사자 탭 렌더 + 통합
**Files:** `court_auction_detail.py`(detail 합성), `web/detail.*`; Test
- [ ] `/api/listing/detail` 응답에 tenants/parties 포함(지연·옵션 호출 고려, 비용↑ 주의). 임차인/등기 탭 렌더(현재 placeholder).
- [ ] 데이터 없으면 숨김. 라이브 검증. 회귀·전체 테스트. 커밋.

---

## 통합·배포
- [ ] 전체 테스트 `python -m unittest discover -s tests`(UTF-8) 통과.
- [ ] opus 코드리뷰(저자/리뷰 분리). 라이브 스모크. main 머지+푸시 또는 PR(사용자 확인).

## Self-Review / 리스크
- C는 보유 데이터/엔드포인트 재사용 → 견고·우선. C3는 외부 키 의존(흡수).
- B-link/B-full은 **BL0(encParam)** 가 게이트. 정적 키 가정 검증 전엔 B 일정 미확정.
- B-full 비용·취약(클라 AES·EUC-KR·레이아웃)·유지보수 부담 — BL0 결과로 범위 재조정.
