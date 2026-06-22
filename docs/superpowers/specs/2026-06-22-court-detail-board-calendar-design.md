# 설계: 경매 물건 상세·풍부한 게시판·월별 캘린더 (§1)

작성일: 2026-06-22
대상: 배포본 `부동산 메물 자동 검색` (210.mapsaihelp.com) **제자리 업데이트**
관련: [경매마당_정밀분석.md](../../경매마당_정밀분석.md), [SPEC.md](../../SPEC.md)

## 1. 배경 & 문제

저번 매물 보드가 "아쉬웠던" 근본 원인: **온비드 공매 API 단일 소스**라 사진·권리분석·실거래·현황이 비어 카드가 placeholder("매입가 협의", "층수·주차 - · -")로 채워졌다. 경매마당이 풍부한 이유는 **대법원 법원경매정보(courtauction.go.kr)**를 원본으로 쓰기 때문.

**데이터 전략은 B(정식 출처)로 확정.** 경매마당을 크롤링하지 않고 대법원 원출처에서 직접 수집한다. 더 합법적(원출처)이고 안정적이며, 사진이 응답에 base64로 임베드되어 제3자 CDN 핫링크가 불필요하다.

## 2. 범위

**이번 §1만 구현** (나머지는 후속 spec):
- ✅ courtauction **상세** 수집기 (사진·현황·기일·권리/인수사항)
- ✅ courtauction **목록** 수집기 보강 (상세 조회에 필요한 키 확보)
- ✅ courtauction **기일별 캘린더** 집계 (월별 진행건수·법원별)
- ✅ 데이터 모델 확장 (사진·현황·기일·권리)
- ✅ 사진 저장/서빙
- ✅ 웹: 풍부한 **경매검색 게시판** · **물건 상세** · **월별 캘린더** (승인된 v2 샘플 기준)
- ✅ 기존 모듈 재사용 연결 (실거래·심평원·체크리스트·리포트)

**후속 (별도 spec):** §2 병원 적합 분류 고도화·병원추천 게시판 / §3 공매(온비드) 캘린더 통합 / §4 직접 의뢰 + 관리자 검토 / §5 상세 리포트(제안서 형식) 자동 생성.

**비범위:** 경매마당 데이터 재사용, 로그인/회원, 결제, 실시간 푸시.

## 3. 데이터 소스 (라이브 검증 완료 2026-06-22)

| 소스 | 엔드포인트 | 키/본문 | 비고 |
|---|---|---|---|
| 경매 목록 | `pgj/pgjsearch/searchControllerMain.on` | `dma_srchGdsDtlSrchInfo`(법원·기간·용도…) | 기존 `court_auction.py`. `totalCnt`·`dlt_srchResult` |
| 경매 상세 | `pgj/pgj15B/selectAuctnCsSrchRslt.on` | `dma_srchGdsDtlSrch{csNo,cortOfcCd,dspslGdsSeq,...}` | **신규**. 아래 §4 응답 구조 |
| 기일별 | `pgj/pgj153/selectDxdyRletSrchRslt.on` | `dma_srchRletDxdy{cortOfcCd,bidDvsCd:"000331"}` | **신규**. 법원별 기일 날짜 목록 |
| 실거래 | 국토부 실거래 API | 주소 | 기존 `market_price.py` |
| 주변 의료 | 심평원 병원·약국 API | 동·좌표 | 기존 `medical_nearby.py` |

세션: `index.on` 선호출로 쿠키 확보 후 호출(기존 `_live_search` 패턴 재사용). 호출 컨텍스트(Referer)에 민감 — 검색 계열은 물건상세검색 페이지 기준 헤더 유지.

### 상세 응답 `data.dma_result` 핵심 (검증됨)
- `csBaseInfo` — 법원·사건번호·청구액·접수일·진행상태
- `dspslGdsDxdyInfo` — 감정가 `aeeEvlAmt`·차수별 최저가·유찰 `flbdNcnt`·매각기일·**인수권리 `ndstrcRghCtt`**·선순위 `tprtyRnkHypthcStngDts`·제시외 `sprfcExstcDts`·물건비고·**매각물건명세서 전자문서ID `dspslGdsSpcfcEcdocId`**
- `csPicLst[]` — 사진 N장: `picFile`(base64 JPEG)·`cortAuctnPicDvsCd`(구분)·`cortAuctnPicSeq`
- `gdsDspslDxdyLst[]` — 기일내역: `dxdyYmd`·`tsLwsDspslPrc`·`auctnDxdyRsltCd`(002=유찰)·`auctnDxdyKndCd`(02=매각결정)
- `gdsDspslObjctLst[]` — 면적·주소·좌표·건물상세·도로명·대표지번
- `aeeWevlMnpntLst[]` — 현황(감정평가 요항): `aeeWevlMnpntItmCd`·`aeeWevlMnpntCtt`
- `rgltLandLstAll` — 토지이용/규제

현황 요항 코드 매핑: 00083001 위치/주위환경 · 00083003 교통 · 00083005 인접도로 · 00083006 이용상태 · 00083009 토지형상 · 00083011 토지이용계획 · 00083014 공부차이 · 00083015 건물구조 · 00083017 설비 · 00083026 임대관계.

## 4. 데이터 모델 확장

`models.py`는 `frozen` `Listing` 유지(목록/카드용). **상세는 별도 구조**로 분리(고응집·저결합, 사진 base64 등 무거운 데이터를 목록에서 분리).

```
@dataclass(frozen=True)
class AuctionDetail:
    identity: str            # "court:{csNo}-{seq}"
    court: str; dept: str; case_no: str
    addr_road: str; addr_jibun: str
    usage: str; auction_type: str
    land_m2: float|None; bldg_m2: float|None
    appraisal: int|None; min_bid: int|None; deposit: int|None; claim_amt: int|None
    fail_count: int|None; sale_date: str|None
    open_ymd, appraise_ymd, dividend_ymd: str|None
    photos: list[Photo]          # 로컬 저장 경로 + 구분
    status_items: list[StatusItem]   # 현황 요항 (label,text)
    bid_history: list[BidEvent]      # 기일내역 (date,low,result)
    incumbrances: list[str]          # 인수사항/권리 (ndstrcRghCtt 파싱)
    senior_rights: str|None
    doc_ecid: str|None               # 매각물건명세서 전자문서ID
    coords: tuple[float,float]|None
```

`Listing`에 카드용 경량 필드만 추가: `thumbnail_path: str|None`, `photo_count: int|None`, `incumbrance_tags: list[str]`(예: 선순위임차인·임차권등기·선순위가등기). 권리 태그는 인수사항 텍스트에서 키워드 추출.

저장: 기존 `store.py`(SQLite)에 `auction_detail` 테이블 + `photo` 메타 테이블 추가. 사진 바이너리는 DB가 아니라 파일로(아래 §6).

## 5. 수집기

- **`court_auction.py` (보강)** — `_listing_from_item`이 상세 조회용 키(`csNo`=srnSaNo, `cortOfcCd`=boCd, `dspslGdsSeq`=maemulSer), 좌표(wgs84), 면적(minArea/maxArea), 건물구조(pjbBuldList)까지 `Listing`에 담는다.
- **`court_auction_detail.py` (신규)** — `fetch_detail(cs_no, cort_ofc_cd, gds_seq) -> AuctionDetail`. 위 응답 파싱 + 현황 코드 매핑 + 기일 결과코드 매핑 + 인수사항→권리태그 추출. 실패는 None 흡수.
- **`court_calendar.py` (신규)** — `month_counts(courts, ym) -> {date:{court:count}}`. 법원별 `selectDxdyRletSrchRslt`로 기일 날짜 목록 → 날짜별 `searchControllerMain` `totalCnt` 집계. 캐시(일 1회). 전국은 법원 집합 합산.

수집 흐름: 목록 스캔 → 신규/관심 물건만 상세 보강(전건 상세 호출 회피, 비용·차단 관리) → 카드 썸네일은 상세의 1번 사진.

## 6. 사진 저장/서빙

base64 `picFile` 디코딩 → `data/photos/{identity}/{seq:02d}.jpg` 저장. 카드 썸네일은 건물 외관 우선 정렬(구분코드 우선순위). 웹은 신규 `/api/photo?id=&n=`(또는 정적 매핑)로 로컬 서빙 — 원출처 CDN 직접 노출 안 함. 권리/저작 안전을 위해 원문 문서(명세서·감정서)는 **저장 대신 courtauction 링크**.

## 7. 웹 (승인된 v2 샘플 기준)

승인 샘플: `부동산매물 자동 검색v2/sample/`(보드·상세·캘린더). 이 HTML/CSS/JS를 배포본 `web/`의 기준 디자인으로 이식. 기존 `web/index.html`+`app.js`(stdlib `http.server`) 구조 유지.

- **경매검색 게시판** — 카드: 썸네일·용도·병원적합 배지·감정가→최저가(하락률)·권리 리스크 태그·유찰·매각일 D-day. 필터 칩(병원적합·근린상가·면적·유찰).
- **물건 상세** (카드 클릭 모달/페이지) — 사진 갤러리·기본내역·가격/실거래(국토부)·**권리분석 인수사항 원문**·기일내역(하락 그래프)·현황 요항·병원적합 등급·**주변 의료(심평원)**·공식문서 링크.
- **월별 캘린더** ("월별일정" 탭) — 경매일정/경매신건/매각결과 탭·월 그리드(일자별 진행건수)·법원/지역 토글·법원별 카운트. 날짜 클릭 → 그날 매각 물건 게시판 필터.

## 8. API 엔드포인트 (web_server.py 추가)

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/api/listings` | (기존) 목록 — court 풍부 필드 포함 |
| GET | `/api/listing/detail?id=` | (신규) AuctionDetail JSON |
| GET | `/api/photo?id=&n=` | (신규) 로컬 사진 서빙 |
| GET | `/api/calendar?ym=&scope=` | (신규) 월별/법원별 집계 |
| GET | `/api/nearby/medical?id=` | (연결) 심평원 주변 의료 |

기존 `/api/verify`·`/api/report`·`/api/checklist/*`·`/api/documents/*` 재사용.

## 9. 기존 모듈 재사용 매핑

| 화면 요소 | 기존 모듈 | 변경 |
|---|---|---|
| 실거래 매매/전세 | `market_price.py` | 상세에 연결 |
| 주변 병원·약국 | `medical_nearby.py` | 상세 패널에 연결 |
| 병원 적합성 | `hospital_fit.py`·`checklist.py` | 상세 등급 표시 |
| 매입 계산 | `finance.py` | 상세 버튼 유지 |
| 공공데이터 검증 | `verify.py`·`public_data.py`·`building_ledger.py`·`land_info.py` | 유지 |
| 리포트 | report(`/api/report`) | §5에서 제안서 형식 확장 |

## 10. 에러 처리 & 사이트 변경 내성

- 모든 외부 호출 실패는 빈 결과/None 흡수(배치 중단 방지) — 기존 패턴 준수.
- 상세 응답 필드명이 바뀌면 해당 카드만 경량 표시로 폴백(목록 데이터 유지).
- 사진 디코딩 실패 시 썸네일 생략(placeholder), 나머지 정상.
- 호출 간격·일일 상세 호출 상한으로 차단 위험 관리.

## 11. 테스트 (TDD)

- 픽스처: `samples/court-detail-2024ta58264.sample.json`(base64 제외 구조) + 실응답 일부.
- 단위: 상세 파서(현황 매핑·기일 결과코드·인수사항→태그·면적/가격), 캘린더 집계, 사진 정렬, 권리태그 추출.
- 통합: `/api/listing/detail`·`/api/calendar`·`/api/photo` 응답.
- 회귀: 기존 `tests/` 통과 유지(목록·체크리스트·verify·medical_nearby).
- 라이브 호출은 fetcher 주입으로 모킹(기존 `court_auction.py` `SearchFetcher` 패턴).

## 12. 제자리 반영 순서

1. v2 샘플 자산(`sample/`, `samples/` 픽스처)을 배포본으로 이관.
2. `court_auction_detail.py` + 파서 + 테스트(RED→GREEN).
3. `Listing`/`AuctionDetail` 모델·`store.py` 스키마 확장 + 마이그레이션.
4. `court_auction.py` 키 보강.
5. 사진 저장 파이프라인 + `/api/photo`.
6. `court_calendar.py` + `/api/calendar`.
7. `/api/listing/detail` + 상세 파이프라인.
8. 웹 이식: 게시판 카드 → 상세 → 캘린더 (샘플 기준).
9. 회귀 테스트 + 로컬 검증 + 배포.

## 13. 리스크 (재진단 2026-06-22)

| # | 리스크 | 확률 | 영향 | 돈? | 완화 |
|---|---|---|---|---|---|
| R1 | courtauction 개편 → 엔드포인트/필드 변경 | 중-저 (대개편은 드묾, 2023 WebSquare 개편 전례) | 높음(수집 중단) | ✗ | 방어적 `.get` 파싱 · 알려진 사건으로 일일 스모크 헬스체크(실패 시 Gmail 알림) · 실패는 빈결과 흡수 · 온비드/직접등록을 폴백 소스로 유지 |
| R2 | 상세 호출 대량화 → IP 차단/Rate limit | 중 (전건 매회 조회 시) | 중-높음(일시 차단) | ✗ | **신규/관심 물건만 상세 조회**(전건 ✗) · 호출 간격(1~2s) · 상세 캐시(변경 없으면 재조회 ✗) · 일일 상한 · 세션 쿠키 재사용 |
| R3 | 사진 저장 용량 | 중 | 중 | **△ 유일하게 돈 가능** | 1물건 17장≈5~8MB. **압축(품질70·최대1280px)→1~2MB** · 병원적합 후보만 저장 · 썸네일+일부만 로컬, 나머지 링크 · 종료/매각 물건 사진 정리 · 증가 시 오브젝트 스토리지(R2/S3) |
| R4 | 전국 캘린더 집계 호출량(법원×날짜) | 중 | 낮-중(느림/R2 유발) | ✗ | **돈 안 듦(무료 정부 API)** · 일 1회 사전계산 캐시 · 서울권 우선 · 기일 있는 날짜만 카운트(빈날 ✗) |

### 비용(돈) 정리
- **외부 API는 전부 무료**: courtauction(정부, 키 불필요), data.go.kr 실거래·심평원·건축HUB, 브이월드, 카카오(무료 한도) — 호출당 과금 없음. R1·R2·R4의 "비용"은 **호출 횟수/시간/차단 위험**(연산 비용)이지 돈이 아니다.
- **돈이 드는 유일 지점 = R3 사진 저장**: Render 영구 디스크는 유료 애드온(용량 과금)이고 무료 디스크는 재배포 시 휘발. 압축+후보한정+정리로 수백 MB 내 억제하면 소액/소형 디스크로 충분.
- **호스팅(Render)** 은 이미 운영 중인 기존 비용 — §1로 추가되는 정기 과금은 없음(사진 저장 정책에 따른 디스크만 변수).

## 14. 성공 기준

- 경매 카드에 실제 사진·감정가/최저가·하락률·권리태그가 표시된다(placeholder 0).
- 상세에서 사진 N장·현황·기일·인수사항 원문·실거래·주변 의료가 보인다.
- 월별 캘린더에 일자별 진행건수·법원별 카운트가 표시된다.
- 기존 기능(체크리스트·verify·매물장·리포트) 회귀 없음.
