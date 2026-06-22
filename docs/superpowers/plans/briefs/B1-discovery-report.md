# B1 역공학 검증 리포트 — 당사자·임차인 데이터 출처 (2026-06-22)

> 목적: spec 3절 "B1(검증) — courtauction 당사자/임차인 엔드포인트 라이브 역공학"을 실제 UI 세션 캡처로 수행.
> 방법: Playwright로 courtauction.go.kr 물건상세검색 → 아파트 상세(서울중앙 2008타경25092) 진입 → 문서 버튼 클릭 → 네트워크 캡처.

## 결론 (확정)

**구조화된 임차인/당사자 JSON API는 존재하지 않는다.** 임차인현황(전입·확정·배당·보증금·대항력)·당사자(채무자/채권자)·권리분석은 전부 **PDF 문서**에만 있다.

### 1. 상세 응답(`pgj/pgj15B/selectAuctnCsSrchRslt.on`)에는 없다
- 아파트(임차인 가능성 높은 물건) 상세 응답의 `dma_result` 키는 빈 단독주택 샘플과 동일: `csBaseInfo, dstrtDemnInfo, dspslGdsDxdyInfo, picDvsIndvdCnt, csPicLst, gdsDspslDxdyLst, gdsDspslObjctLst, rgltLandLstAll, bldSdtrDtlLstAll, gdsNotSugtBldLsstAll, gdsRletStLtnoLstAll, aeeWevlMnpntLst`.
- 임차/전입/확정/보증금/채무자/채권자/당사자/대항/배당요구/점유 → 구조화 필드 **0건**.
- 유일한 임차 신호: `aeeWevlMnpntLst`의 `00083026`(기타참고사항/임대관계) **자유텍스트** (예: "임대관계 미상임").

### 2. 임차인·권리·점유는 PDF 문서에 있다 (ecfs 전자문서 뷰어)
- **매각물건명세서** 버튼(`btn_dspslGdsSpcfc1`) → 새 탭 `ecfs.scourt.go.kr/sgvo/.../SGVO201M01.xml?paramData=base64({"encParam":"...","pspTkn":"NA","pspSid":"NA"})`.
- **현황조사서** 버튼(`btn_curstExmndcTop`) → 동일 ecfs 뷰어 흐름. (감정평가서도 동일.)
- 뷰어 내부 호출 체인:
  1. `ecfs.../sgvomain/selectDocVwrInf.on` — 뷰어 정보
  2. `ecfs.../sgvomain/getPdf.on` → `{streamdocsId, accessToken(JWT), dlt_edms:[{ecdocId, fileEdmsDocId, cortCd, ...}]}`
  3. `pvo.scourt.go.kr/streamdocs/v4/documents/{streamdocsId}/renderings/N` — 페이지 **JPEG 이미지**
  4. `pvo.scourt.go.kr/streamdocs/v4/documents/{streamdocsId}/texts/N` — **텍스트 레이어 JSON**(글자 단위 text + rect 좌표, **EUC-KR 인코딩**)

### 3. 핵심 장애물: `encParam`은 클라이언트 JS에서 생성
- 매각물건명세서/현황조사서 클릭 시 courtauction 쪽에서 **encParam 생성용 서버 호출이 없음** → 브라우저 JS가 상세 데이터(ecdocId 등)를 **클라이언트측 AES 암호화**해 ecfs로 넘긴다(키는 courtauction JS 번들 내부).
- 우리가 이미 보유: `dspslGdsSpcfcEcdocId`(= 매각물건명세서 ecdocId, parse_detail의 `doc_ecid`). getPdf 응답의 `dlt_edms[0].ecdocId`와 대응.

## B 실현가능성 평가

| 경로 | 내용 | 비용 | 견고성 |
|---|---|---|---|
| **B-full** | encParam 재현 → getPdf → PDF 다운로드/`texts` → 임차인 표·권리 구조화 파싱 | 높음 | 낮음(클라 AES·EUC-KR·레이아웃 의존) |
| **B-link** | encParam 재현으로 공식 문서 뷰어 **바로가기 버튼**만 제공(파싱 없음) | 중간(encParam 재현 공유) | 높음(원문 그대로) |
| **B-defer** | B 보류, 자유텍스트 임대관계만 노출 + C(시세·주변통계) 우선 | 낮음 | 높음 |

- encParam 재현이 B-full/B-link 공통 난관. 정적 AES 키면 1회 역공학 후 견고, 동적이면 헤드리스 브라우저 1회 구동/물건 필요(무겁다).
- madangs는 이 PDF들을 파싱해 임차인/권리분석을 만든다(= B-full 수준 투자).

## 권장 (사용자 결정 필요)
1. **저비용 고가치 먼저(C)**: 시세분석 탭(market_price 보유) + 주변 매각통계(자체 수집 데이터 집계) — 견고·즉시.
2. **B는 B-link MVP → 필요 시 B-full**: 공식 매각물건명세서/현황조사서 바로가기부터(원문이 가장 신뢰도 높음), 구조화 임차인 표는 후속.

## 캡처 아티팩트(세션 한정, 미커밋)
- 아파트 상세 응답, getPdf 응답, texts/0 레이어 → v2 작업폴더 임시. 필요 시 재캡처 가능(헤더 fix 적용된 court_auction_detail로).
