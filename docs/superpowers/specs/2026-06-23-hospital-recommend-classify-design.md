# §2 병원추천 게시판 · 적합 분류 고도화 — 설계

작성일: 2026-06-23
관련 메모: 병원매물 진행 상태(§2 로드맵)

## 1. 목표

매물의 **병원(정형외과) 적합도 분류를 정교화**하고, 그 위에 **복합 추천 점수로 매물을 랭킹하는 "🏥 추천" 게시판**을 만든다. 사용자 결정에 따라 **Phase 1(분류 정확도) → Phase 2(추천 랭킹)** 순으로 구현한다.

확정된 설계 결정(브레인스토밍):
- 범위: 분류 고도화 + 추천 랭킹 **둘 다**, 분류 먼저.
- 데이터 전략: **하이브리드** — 전 매물은 무료 신호로 베이스라인, **상위 후보 N건만 공공데이터 자동 검증**(캐시).
- 기준: **정형외과 기본 + 가중치 파라미터화**(named profile, 향후 다른 과 확장 여지).
- 노출: 보드에 **새 "🏥 추천" 탭** 신설(복합 점수 순위 카드).

## 2. 현재 상태(요약)

- `hospital_fit.classify(listing)` — `usage`·`title` **키워드만**으로 4단계(open/build/check/unfit). 공공데이터 미사용. `web_server._listing_to_dict`에서 직렬화 시 매번 계산, DB 저장 안 함.
- 체크리스트 등급(A~D/부적합, `checklist.py`)은 공공데이터 기반으로 정교하나 **사용자가 매물마다 직접 검증 실행**해야 산출되고 **매물장에서만** 노출.
- "추천"은 사실상 `web/app.js` `renderPriority()`의 **월세 오름차순 상위 3건**이 전부. 복합 점수·추천 탭 없음.
- 외부 호출 보호 인프라 기존재: `_ext_cache`(300s)·`_ext_fetch_sema`(동시 4)·시간예산, 수집 스냅샷 캐시+백그라운드 수집 패턴.

## 3. Phase 1 — 적합 분류 고도화 (`hospital_fit.py`)

### 3.1 시그니처 확장
```python
def classify(listing, *, zoning: str | None = None, main_purpose: str | None = None) -> dict:
    # 반환: {"level", "label", "reason", "fit_score"}  # fit_score: 0~100 int
```
- 기존 호출부와 호환(키워드 인자는 선택). `web_server._listing_to_dict`는 해당 매물에 검증 데이터(`land.zoning_names`, `building.main_purpose`)가 있으면 전달해 분류를 정밀화한다. 없으면 키워드 폴백.

### 3.2 공공데이터 기반 판정 규칙
용도지역(zoning) → 적합 경향:
- 상업지역(중심/일반/근린/유통상업), 준주거지역 → **개원 유리**
- 일반주거지역(1·2·3종) → 개원 가능(근생 입점 허용)
- 전용주거지역(1·2종) → 개원 **불리**(근린생활 제한)
- 녹지/관리/자연환경보전 → **신축(build) 후보**(건물 입점 부적합)
- 농림지역 → **부적합 경향**(의료시설 신축 제약)

건축물 주용도(main_purpose) → 적합 경향:
- 제1·2종근린생활시설, 의료시설, 업무시설, 판매시설 → **open**
- 단독주택/공동주택/주거 → **check**(1층 전환·철거 신축 검토)
- 공장/창고/위험물저장 → **check/build**(철거 신축 검토)

판정 합성: 건축물 주용도가 있으면 그것을 1차 근거로 level 결정, 용도지역으로 보정. 둘 다 없으면 키워드 폴백.

### 3.3 키워드 폴백 개선
- 용어 정규화: "근생"·"1종근생"·"2종근생"·"근린생활" → 근린생활시설로 동일 취급. 기존 `_COMMERCIAL`/`_BUILDABLE_LAND`/`_RESIDENTIAL`/`_UNFIT` 유지·보강.

### 3.4 fit_score 산출(0~100)
- level 기본점: open 75, build 55, check 35, unfit 5.
- 보정(데이터 가용 시): 상업/준주거 +15, 일반주거 +5, 전용주거 −10; 주용도 근린생활/의료 +10, 주거 −5.
- `clamp(0, 100)`. 버킷(level)은 필터용으로 유지, fit_score는 랭킹 입력.

## 4. Phase 2 — 병원추천 랭킹 + 게시판

### 4.1 신규 모듈 `recommend.py`(순수 함수)
복합 추천 점수(0~100)를 가중 합산. 각 신호는 0~1 정규화 sub-score로 변환.

| 신호 | sub-score 정의 | 정형외과 가중 | 가용성 |
|---|---|---|---|
| fit | `fit_score/100` | 0.30 | 전 매물(무료) |
| grade | A=1.0,B=.75,C=.5,D=.25,부적합=0 | 0.20 | 검증된 매물만 |
| price | 시세대비: ratio=매물㎡당가/시세평균; ≤0.8→1.0, ≥1.4→0.0, 그 사이 선형 | 0.15 | 상위후보 검증 |
| competition | 정형외과 수 0→1.0,1→0.7,2→0.4,≥3→0.1 | 0.15 | 상위후보 검증 |
| discount | 경매 할인율=(감정가−최저가)/감정가; 0%→0,≥50%→1.0 선형 | 0.10 | 경매 전 매물(무료) |
| location | 정형외과 입지(주차 충분·재활 연면적·1층 접근·약국 인접 평균) | 0.10 | 부분 가용 |

정규화: `score = Σ(wᵢ·sᵢ) / Σ(wᵢ over available i) · 100`. **누락 신호는 가중에서 제외**(패널티 없음). 가중치는 `PROFILES["ortho"]` dict로 정의, 기본 ortho.

- `baseline_score(listing, fit, *, profile)` — 무료 신호(fit·discount·가용 location)만.
- `enriched_score(listing, fit, verify_data, grade, *, profile)` — 검증 신호(grade·price·competition) 포함.

### 4.2 서버 `/api/recommend`
- 쿼리: `profile`(기본 ortho), `limit`(자동검증 상위 N, 기본 10), 보드 스코프(조건일치/수집전체).
- 흐름(하이브리드):
  1. 캐시된 수집 스냅샷에서 **전 매물 베이스라인 점수** 즉시 계산·정렬(외부호출 없음, 빠름).
  2. **상위 N건만** `verify_address`+심평원 자동 검증 → `enriched_score`로 재점수·재정렬. 기존 `_ext_cache`·세마포어·시간예산 재사용, 결과 캐시.
  3. 검증이 시간예산 내 미완료면 **베이스라인 반환 + 백그라운드 보강**(기존 스냅샷 패턴과 동일, 다음 요청에서 갱신).
- 응답(매물별):
```json
{"recommend": {"score": 0-100, "rank": 1, "enriched": true,
  "breakdown": {"fit":.., "grade":.., "price":.., "competition":.., "discount":.., "location":..},
  "summary": {"fit_label":"개원 가능","grade":"B","market_note":"시세 −12%","competition_note":"정형외과 1곳"}}}
```
플러스 `{"profile":"ortho","enriched_count":N,"generated_at":...}`.

### 4.3 UI — 새 "🏥 추천" 탭
- `web/index.html`: 보드 필터 탭에 "🏥 추천" 버튼 추가.
- `web/app.js`: `boardFilter="recommend"` + `renderRecommendBoard()`. 순위(#)·복합점수 헤더, 적합도/등급 배지, 시세·경쟁의원·할인율 요약 칩. **기존 카드 컴포넌트 재사용**.
- 상위 N건 "자동검증됨" 배지, 나머지 "기본점수" 표기로 하이브리드 상태를 투명하게.
- (선택) 현황의 `renderPriority()`는 그대로 두거나 복합 점수 top3로 교체 — Phase 2 말미 결정.

## 5. 모듈 경계(isolation)

| 모듈 | 책임 | 의존 |
|---|---|---|
| `hospital_fit.py` | 강화된 분류 + fit_score(순수) | models |
| `recommend.py`(신규) | 복합 점수·가중 프로필(순수) | hospital_fit 출력·verify 출력(값으로 주입) |
| `web_server.py` | `/api/recommend` 오케스트레이션(베이스라인+상위N 보강) | recommend·verify·store·캐시 인프라 |
| `web/app.js`·`index.html` | 추천 탭·렌더 | 기존 카드 컴포넌트 |

`recommend.py`는 외부 호출/IO 없이 값만 받아 점수를 내는 순수 모듈로, 단독 테스트 가능.

## 6. 데이터 흐름
수집 스냅샷(캐시) → `hospital_fit`(키워드) → `baseline_score` → 정렬 → 상위 N: `verify_address`+심평원(캐시) → `hospital_fit`(공공데이터 보완) + `enriched_score` → 재정렬 → 응답 → `renderRecommendBoard`.

## 7. 에러 처리
- 상위 후보 검증 실패/타임아웃: 해당 매물은 **베이스라인 점수로 그레이스풀 강등**, `summary`에 "검증 보류" 표기(에러 삼키지 않음).
- 외부 API 키 없음/실패: price·competition 신호는 제외(가중 재정규화), fit·discount로만 점수. 응답은 항상 성공.
- 잘못된 입력(빈 스냅샷): 빈 목록 + 안내.

## 8. 테스트(기존 246 통과 유지)
- `hospital_fit`: zoning×main_purpose 조합 판정, 키워드 폴백/용어변이, fit_score 범위·단조성.
- `recommend`: 베이스라인 vs 정밀 점수, 누락 신호 정규화(패널티 없음), ortho 프로필 가중, 랭킹 순서, 경계값(시세 ratio·경쟁수·할인율).
- `/api/recommend` 통합: json_file 픽스처로 베이스라인 랭킹 반환·정렬 검증.

## 9. 범위 밖(YAGNI)
- 전 매물 백그라운드 일괄 공공데이터 검증(API 비용·속도).
- 다과목 동시 운영 UI(가중치는 코드 프로필로 시작).
- 추천 가중치 수동 편집 UI.
- 추천 점수 DB 영속화(요청 시 캐시 기반 계산; 필요해지면 후속).

## 10. 구현 순서(plan 입력)
1. Phase 1: `hospital_fit` 강화 + 단위 테스트 → `_listing_to_dict` 연결.
2. Phase 2a: `recommend.py` 순수 함수 + 단위 테스트.
3. Phase 2b: `/api/recommend` 엔드포인트(베이스라인) + 통합 테스트.
4. Phase 2c: 상위 N 하이브리드 보강(캐시/세마포어/예산 재사용).
5. Phase 2d: "🏥 추천" 탭 UI(`index.html`·`app.js`).
6. 라이브 검증 + opus 코드리뷰.
