# 설계: 체크리스트 기반 매물 검토 구조

> 작성일: 2026-06-12 · 상태: 승인됨
> 근거 문서: [병원건물_매입_신축_체크리스트.md](../../병원건물_매입_신축_체크리스트.md)

## 목표

수집된 매물을 "병원건물 매입·신축 체크리스트"에 맞춰 검토하는 구조로 대시보드를 재설계한다.
공공데이터로 확인 가능한 항목은 자동 판정하고, 나머지는 수동 체크하여 매물별 종합 등급을 산출한다.

## 사용자 결정 사항

1. **검토 방식**: 하이브리드 — 자동 판정(공공데이터) + 수동 체크 + 종합 등급
2. **검토 대상**: 매물장 등록 매물만 (API 호출량 절약)
3. **철거 후 신축 프로필 추가** — 토지 용도·도로 접면·입지만 좋으면 건물 상태 무관
4. **신규 매물 가시성 강화** — 소스별 신규 등록이 잘 보여야 함
5. **필수조건 검색** — 대지 150평↑, 연면적 600평↑, 주차대수 등 조건으로 기존 매물 검색
6. **3D 인터랙션 디자인** 적용 (CSS 3D 트랜스폼 기반)

## 전체 깔때기 구조

```
수집 (네이버·온비드)
  → 신규 매물 강조 (배너·우선 정렬·경과시간·펄스 배지)
  → 필수조건 검색 (평 단위 입력 → 충족/확인필요/미달 3그룹)
  → 매물장 등록
  → 체크리스트 검토 (자동 판정 + 수동 체크 → A/B/C/D/부적합)
```

## 1. 체크리스트 정의 — `realestate_alert/checklist.py` (신규)

항목 정의는 frozen dataclass로 코드에 둔다 (JSON 설정 분리는 YAGNI).

```python
@dataclass(frozen=True)
class ChecklistItem:
    item_id: str          # 예: "zoning", "mri_load"
    category: str         # 입지/법규/권리/물리/재무/신축/철거
    label: str
    description: str      # 판단 기준 안내
    kind: str             # "auto" | "info" | "manual"
    profiles: tuple[str, ...]  # "building" | "rebuild" | "land" 중 적용 대상
    critical: bool = False     # fail 시 즉시 부적합(No-Go)
    weight: float = 1.0
```

### 검토 프로필 3종

| 프로필 | 키 | 적용 카테고리 | critical 항목 |
|--------|----|--------------|--------------|
| 기존 건물 사용(매입) | `building` | 입지·법규·권리·물리·재무 | 용도지역, 위반건축물, 주차, 임차인 명도 |
| 철거 후 신축 | `rebuild` | 입지·토지 법규·권리·신축·철거·재무 | **용도지역, 도로 접면, 입지(수동), 임차인 전원 명도** |
| 나대지 신축 | `land` | 입지·토지 법규·신축·재무 | 용도지역, 도로 접면 |

`rebuild` 프로필에서 건물 물리조건(층고·MRI 하중·차폐·승강기·노후도)은 항목 자체가 제외된다.
노후도는 "철거 대상 — 무관"으로 점수에서 빠진다.

### 자동 판정(auto) 항목과 로직

| item_id | 프로필 | 로직 | critical |
|---------|--------|------|----------|
| `zoning` | 전체 | 전용주거지역 포함 → warn, 조회 성공 → pass, 실패 → unknown | ✅ (fail 조건: 없음 — warn까지만, 최종 판단은 수동 확정 가능) |
| `elevator` | building | 2층 이상 + 승강기 0대 → fail, 있으면 pass | |
| `parking` | building | 대장 주차대수 ≥ 추정 법정대수(연면적/150㎡) → pass, 미달 → warn | |
| `price_market` | building | 매물가/연면적 vs 주변 ㎡당 평균 실거래가, +20% 초과 → warn | |
| `road_access` | rebuild·land | 도로 접면 없음(맹지) → fail, 있으면 pass + 폭 힌트 | ✅ |
| `building_age` | building | 준공 30년 이상 → warn (보강비 변수) | |
| `rebuild_age_ok` | rebuild | 항상 pass — "철거 대상, 노후 무관 (협상 유리)" evidence 표시 | |

### 정보 제공(info) 항목 — 데이터 자동 표시, 판단은 수동 확정

| item_id | 프로필 | 제공 데이터 |
|---------|--------|------------|
| `buildable_volume` | rebuild·land | 대지면적 × 용적률 = 최대 연면적 계산값 |
| `land_price_basis` | rebuild·land | 공시지가 합계, 매물가 대비 배율 |
| `current_use` | building | 건축물대장 주용도 (용도변경 필요 여부 판단용) |

### 수동(manual) 항목 — 체크리스트 문서에서 매물 단위 판단 항목만 발췌 (~20개)

- 입지: 배후 인구·고령 비율, 경쟁 의원, 대중교통, 가시성·간판, 약국 연계
- 법규: 용도변경 가능성, 장애인 편의시설, 소방·피난, 위반건축물(세움터 확인 안내 — API 미지원)
- 권리(building·rebuild): 등기부 권리관계, 임차인 명도(rebuild는 critical), 부가세 특약
- 물리(building만): 층고, MRI 하중·반입, 방사선 차폐, 전기 용량, 기둥 스팬
- 신축(rebuild·land): 일조권·형태 제한, 지반, 인입(상하수·전기·가스), 주차 확보 대지 형상
- 철거(rebuild만): 철거비·석면 조사, 멸실등기 일정, 인접 민원 대비
- 재무: 총사업비 예산 내, 대출 계획

명의 구조·세무사 상담 등 매물 무관 항목은 제외.

## 2. 자동 판정 엔진 — `evaluate_auto_items(listing: dict, report: dict) -> dict`

`verify_address()` 리포트를 입력받아 `{item_id: {"status": "pass|warn|fail|unknown", "evidence": str}}` 반환.
API 호출 없는 순수 함수 — 단위 테스트 용이. 데이터 없으면 `unknown`(미확인) + 수동 확인 유도.

## 3. 점수·등급 — `compute_score(definition, auto, manual, profile)`

- 항목 상태: auto는 pass/warn/fail/unknown, manual은 pass/fail/na/unchecked
- 점수 = Σ(pass×weight + warn×0.5weight) / Σ(판정된 항목 weight) — na·unknown·unchecked 제외
- 등급: A(≥85%) / B(≥70%) / C(≥50%) / D — **critical 항목 fail 1개라도 있으면 즉시 "부적합"**
- 진행률: "자동 7/8 확인 · 수동 5/14 체크"

## 4. 저장 — `store.py`에 `checklist_reviews` 테이블 추가

```sql
CREATE TABLE checklist_reviews (
    identity TEXT PRIMARY KEY,
    review_json TEXT NOT NULL,   -- {profile, auto:{}, manual:{}, evaluated_at}
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

- 자동 판정 결과는 캐시 — 재방문 시 API 재호출 없음, "재검증" 버튼으로만 갱신
- 매물장 삭제 시 검토 데이터도 함께 삭제
- 점수·등급은 저장하지 않고 읽을 때 계산 (정의 변경 시 자동 반영)

## 5. API — `web_server.py`

| 메서드 | 경로 | 동작 |
|--------|------|------|
| GET | `/api/checklist/definition` | 항목 정의 + 프로필 목록 (UI 렌더용) |
| GET | `/api/checklist/reviews` | 전체 검토 요약 `{identity: {grade, score, progress, profile}}` |
| POST | `/api/checklist/evaluate` | `{identity, listing, profile}` → verify 실행 + 자동 판정 저장 + 전체 검토 반환 |
| POST | `/api/checklist/manual` | `{identity, item_id, status, memo}` → 수동 체크 저장 + 갱신된 점수 반환 |

기존 `/api/listings` 응답에 `first_seen_at` 추가 (신규 매물 경과시간 표시용).
`/api/ledger/delete` 시 검토 데이터 동반 삭제.

## 6. UI — `web/` (index.html · app.js · styles.css)

### 6.1 신규 매물 강조
- 상단 배너: "오늘 신규 N건 — 네이버 a건 · 온비드 b건", 클릭 시 신규만 필터
- 신규 매물 보드 최상단 우선 정렬 (등록 시각 역순)
- NEW 배지 + "3시간 전 등록" 상대 시간, 24시간 이내는 강조색+펄스, 24~72시간은 일반 배지
- 신규만 보기 토글

### 6.2 필수조건 검색 패널 (보드 상단)
- 입력: 대지면적≥(평), 연면적≥(평), 주차대수≥, 승강기 유무, 용도지역 키워드, 매물 유형
- 평 입력 → ㎡ 자동 환산 표시 (1평 = 3.305785㎡)
- 프리셋 버튼: "신축용 토지 조건" / "기존 건물 조건"
- 결과 3그룹: ✅ 조건 충족 / ❓ 확인 필요(데이터 없음, 접기 가능) / 미달(카운트만)
- 마지막 입력값 localStorage 유지. 서버 변경 없음 — 클라이언트 필터

### 6.3 체크리스트 검토 (매물장)
- 매물장 항목에 등급 배지(A~D/부적합/미검토) + 진행률 + "체크리스트 검토" 버튼
- 검토 모달: 상단 등급·점수·Go/No-Go, 프로필 선택(매입/철거 후 신축/나대지 신축),
  "자동 검증 실행" 버튼, 카테고리별 섹션, auto 항목 판정 배지+근거,
  manual 항목 3-상태 체크(적합/부적합/해당없음)+메모

### 6.4 3D 인터랙션 (CSS 3D 트랜스폼, 라이브러리 없음)
- 매물 카드: 마우스 추적 틸트 (perspective + rotateX/Y + translateZ + 그림자 확장)
- 등급 배지: 검토 완료 시 rotateY 180° 플립 공개
- 검토 모달: 깊이 진입 전환, 카테고리 섹션 translateZ 계층
- 신규 배너: 레이어 시차 + 카운트 롤링
- 검색 패널: rotateX 폴드 펼침/접힘
- 버튼: active 시 translateZ 하강
- 원칙: transform/opacity만 애니메이션, `prefers-reduced-motion` 시 전체 비활성화

## 7. 테스트

- `tests/test_checklist.py` (신규): 항목 정의 무결성, 프로필 필터, 자동 판정 각 케이스(mock 리포트), 점수·등급 경계값, critical fail → 부적합
- `tests/test_store.py` 확장: checklist_reviews CRUD, 매물장 삭제 연동
- `tests/test_web_server.py` 확장: API 4종 정상/오류 입력
- 구현 후 대시보드 실행해 Playwright로 동작 확인

## 변경 파일 목록

| 파일 | 변경 |
|------|------|
| `realestate_alert/checklist.py` | 신규 — 정의 + 평가 + 점수 |
| `realestate_alert/store.py` | 테이블 + CRUD 추가 |
| `realestate_alert/web_server.py` | API 4종 + first_seen_at + 삭제 연동 |
| `web/index.html` | 배너·검색 패널·검토 모달 마크업 |
| `web/app.js` | 필터·검토 UI·틸트 인터랙션 |
| `web/styles.css` | 3D 인터랙션·배지·패널 스타일 |
| `tests/test_checklist.py` | 신규 |
| `tests/test_store.py`, `tests/test_web_server.py` | 확장 |
| `docs/병원건물_매입_신축_체크리스트.md` | 철거 후 신축 섹션 추가 (완료) |
