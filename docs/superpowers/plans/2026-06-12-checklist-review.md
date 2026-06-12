# 체크리스트 기반 매물 검토 구조 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매물장 등록 매물을 병원건물 체크리스트(3프로필: 매입/철거 후 신축/나대지 신축)로 자동+수동 검토하고, 신규 매물 강조·필수조건 검색·3D 인터랙션을 대시보드에 추가한다.

**Architecture:** 새 모듈 `checklist.py`가 항목 정의·자동 판정·점수 계산을 순수 함수로 담당. `store.py`에 `checklist_reviews` 테이블, `web_server.py`에 API 5종 추가. 프런트는 기존 패턴(상태 객체 + render 함수 + dialog 모달) 그대로 확장.

**Tech Stack:** Python 표준 라이브러리(sqlite3, http.server, dataclasses), unittest, 순수 JS/CSS (라이브러리 없음).

**주의:** 이 프로젝트는 git 저장소가 아니므로 커밋 단계는 생략한다. 각 Task 후 `python -m pytest tests/ -q`로 회귀 확인.

**스펙:** [2026-06-12-checklist-review-design.md](../specs/2026-06-12-checklist-review-design.md)

---

### Task 1: checklist.py — 항목 정의 + 프로필 필터

**Files:**
- Create: `realestate_alert/checklist.py`
- Test: `tests/test_checklist.py`

- [ ] **Step 1: 실패하는 테스트 작성** — `tests/test_checklist.py`

```python
import unittest

from realestate_alert.checklist import (
    CHECKLIST_ITEMS,
    PROFILES,
    definition_payload,
    items_for_profile,
)


class ChecklistDefinitionTests(unittest.TestCase):
    def test_item_ids_are_unique(self):
        ids = [item.item_id for item in CHECKLIST_ITEMS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_items_have_valid_kinds_and_profiles(self):
        for item in CHECKLIST_ITEMS:
            self.assertIn(item.kind, ("auto", "info", "manual"), item.item_id)
            self.assertTrue(item.profiles, item.item_id)
            for profile in item.profiles:
                self.assertIn(profile, PROFILES, item.item_id)

    def test_rebuild_profile_excludes_building_physical_items(self):
        ids = {item.item_id for item in items_for_profile("rebuild")}
        for excluded in ("ceiling_height", "mri_load", "radiation_shield", "elevator", "building_age"):
            self.assertNotIn(excluded, ids)
        for included in ("road_access", "demolition_cost", "tenant_eviction", "zoning"):
            self.assertIn(included, ids)

    def test_rebuild_critical_items(self):
        critical = {item.item_id for item in items_for_profile("rebuild") if item.critical}
        self.assertEqual(critical, {"loc_overall", "zoning", "road_access", "tenant_eviction"})

    def test_unknown_profile_raises(self):
        with self.assertRaises(ValueError):
            items_for_profile("hotel")

    def test_definition_payload_shape(self):
        payload = definition_payload()
        self.assertIn("building", payload["profiles"])
        self.assertTrue(any(item["item_id"] == "mri_load" for item in payload["items"]))
```

- [ ] **Step 2: 테스트 실패 확인** — `python -m pytest tests/test_checklist.py -q` → ModuleNotFoundError
- [ ] **Step 3: 구현** — `realestate_alert/checklist.py`에 `ChecklistItem` frozen dataclass, `PROFILES`, `CATEGORY_ORDER`, `CHECKLIST_ITEMS` 튜플(스펙의 항목표 그대로: 입지 6 + 법규 8 + 권리 3 + 물리 6 + 신축 7 + 철거 4 + 재무 3), `items_for_profile`, `definition_payload` 작성. critical: `loc_overall`(전체), `zoning`(전체), `violation_check`(building), `tenant_eviction`(building·rebuild), `road_access`(rebuild·land).
- [ ] **Step 4: 테스트 통과 확인** — `python -m pytest tests/test_checklist.py -q`

### Task 2: checklist.py — 자동 판정 evaluate_auto_items

**Files:**
- Modify: `realestate_alert/checklist.py`
- Test: `tests/test_checklist.py`

- [ ] **Step 1: 실패하는 테스트 추가**

```python
class EvaluateAutoItemsTests(unittest.TestCase):
    def test_empty_report_yields_unknown(self):
        results = evaluate_auto_items({}, {"building": None, "land": None, "market": None})
        self.assertEqual(results["zoning"]["status"], "unknown")
        self.assertEqual(results["road_access"]["status"], "unknown")

    def test_zoning_exclusive_residential_warns(self):
        report = {"land": {"zoning_names": ["제1종전용주거지역"]}}
        self.assertEqual(evaluate_auto_items({}, report)["zoning"]["status"], "warn")

    def test_zoning_falls_back_to_listing(self):
        results = evaluate_auto_items({"zoning": "준주거지역"}, {})
        self.assertEqual(results["zoning"]["status"], "pass")

    def test_blind_land_fails_road_access(self):
        report = {"land": {"road_side": "맹지"}}
        self.assertEqual(evaluate_auto_items({}, report)["road_access"]["status"], "fail")

    def test_elevator_fail_when_multistory_without_lift(self):
        report = {"building": {"elevator_count": 0, "ground_floors": 5}}
        self.assertEqual(evaluate_auto_items({}, report)["elevator"]["status"], "fail")

    def test_parking_pass_and_warn(self):
        ok = {"building": {"parking_spaces": 14, "total_area_m2": 2000}}
        short = {"building": {"parking_spaces": 5, "total_area_m2": 2000}}
        self.assertEqual(evaluate_auto_items({}, ok)["parking"]["status"], "pass")
        self.assertEqual(evaluate_auto_items({}, short)["parking"]["status"], "warn")

    def test_building_age_warns_after_30_years(self):
        report = {"building": {"approval_year": 1990}}
        results = evaluate_auto_items({}, report, now_year=2026)
        self.assertEqual(results["building_age"]["status"], "warn")

    def test_rebuild_age_always_pass(self):
        results = evaluate_auto_items({}, {"building": {"approval_year": 1985}}, now_year=2026)
        self.assertEqual(results["rebuild_age_ok"]["status"], "pass")
        self.assertIn("철거", results["rebuild_age_ok"]["evidence"])

    def test_price_market_warns_on_premium(self):
        listing = {"deposit": 3_000_000_000, "monthly_rent": 0, "building_area_m2": 1000}
        report = {"market": {"avg_price_per_m2": 2_000_000}}
        self.assertEqual(evaluate_auto_items(listing, report)["price_market"]["status"], "warn")

    def test_buildable_volume_info(self):
        report = {"building": {"plat_area_m2": 500}}
        result = evaluate_auto_items({"floor_area_ratio": 200}, report)["buildable_volume"]
        self.assertEqual(result["status"], "info")
        self.assertIn("1,000", result["evidence"])
```

- [ ] **Step 2: 실패 확인** — ImportError(evaluate_auto_items)
- [ ] **Step 3: 구현** — `evaluate_auto_items(listing, report, now_year=None)` + 항목별 내부 판정 함수(`_judge_zoning`, `_judge_elevator`, `_judge_parking`, `_judge_building_age`, `_judge_rebuild_age`, `_judge_road_access`, `_judge_price_market`, `_info_current_use`, `_info_buildable_volume`, `_info_land_price`). 모든 함수는 데이터 없으면 `unknown` + 확인 안내 evidence. 매물가는 `monthly_rent == 0 and deposit > 0`일 때 deposit을 매매가로 간주.
- [ ] **Step 4: 통과 확인**

### Task 3: checklist.py — 점수·등급 compute_review

**Files:**
- Modify: `realestate_alert/checklist.py`
- Test: `tests/test_checklist.py`

- [ ] **Step 1: 실패하는 테스트 추가**

```python
class ComputeReviewTests(unittest.TestCase):
    def test_critical_fail_forces_no_go(self):
        auto = {"road_access": {"status": "fail", "evidence": "맹지"}}
        review = compute_review("land", auto, {})
        self.assertEqual(review["grade"], "부적합")
        self.assertTrue(review["no_go"])

    def test_all_pass_scores_grade_a(self):
        items = items_for_profile("land")
        auto = {i.item_id: {"status": "pass", "evidence": ""} for i in items if i.kind == "auto"}
        manual = {i.item_id: {"status": "pass", "memo": ""} for i in items if i.kind in ("manual", "info")}
        review = compute_review("land", auto, manual)
        self.assertEqual(review["grade"], "A")
        self.assertEqual(review["score"], 100.0)

    def test_unchecked_and_na_excluded_from_score(self):
        review = compute_review("land", {"zoning": {"status": "pass", "evidence": ""}}, {})
        self.assertEqual(review["score"], 100.0)  # 판정된 항목이 zoning뿐
        self.assertEqual(review["grade"], "A")

    def test_no_judged_items_yields_ungraded(self):
        review = compute_review("land", {}, {})
        self.assertIsNone(review["score"])
        self.assertIsNone(review["grade"])

    def test_warn_counts_half(self):
        auto = {"zoning": {"status": "warn", "evidence": ""}}
        review = compute_review("land", auto, {})
        self.assertEqual(review["score"], 50.0)
        self.assertEqual(review["grade"], "C")

    def test_progress_counts(self):
        auto = {"zoning": {"status": "pass", "evidence": ""}, "road_access": {"status": "unknown", "evidence": ""}}
        manual = {"loc_overall": {"status": "pass", "memo": ""}}
        review = compute_review("land", auto, manual)
        self.assertEqual(review["progress"]["auto_done"], 1)
        self.assertEqual(review["progress"]["manual_done"], 1)

    def test_items_include_definition_and_state(self):
        review = compute_review("building", {}, {"mri_load": {"status": "fail", "memo": "보강 불가"}})
        row = next(item for item in review["items"] if item["item_id"] == "mri_load")
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["memo"], "보강 불가")
        self.assertEqual(row["category"], "물리")
```

- [ ] **Step 2: 실패 확인** → ImportError(compute_review)
- [ ] **Step 3: 구현** — `compute_review(profile, auto_results, manual_results)`:
  - auto 항목: 상태 pass/warn/fail/unknown, unknown은 점수 제외. info 항목: evidence는 auto 결과에서, 점수 상태는 manual 결과에서.
  - 점수 = (passΣweight + 0.5×warnΣweight) / 판정된 항목 Σweight × 100, 소수 1자리.
  - 등급 A≥85 / B≥70 / C≥50 / D, critical fail 시 `부적합` + `no_go=True`. 판정 0건이면 score/grade None.
  - 반환: `{profile, score, grade, no_go, progress{auto_done,auto_total,manual_done,manual_total}, items[]}` — items는 정의 + status + evidence + memo 병합.
- [ ] **Step 4: 통과 확인** — `python -m pytest tests/test_checklist.py -q`

### Task 4: store.py — checklist_reviews 테이블

**Files:**
- Modify: `realestate_alert/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: 실패하는 테스트 추가**

```python
class ChecklistReviewStoreTests(unittest.TestCase):
    def test_save_get_roundtrip_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            review = {"profile": "rebuild", "auto": {}, "manual": {"loc_overall": {"status": "pass", "memo": ""}}}
            store.save_checklist_review("manual:yc-001", review)
            self.assertEqual(store.get_checklist_review("manual:yc-001")["profile"], "rebuild")
            store.save_checklist_review("manual:yc-001", {**review, "profile": "building"})
            self.assertEqual(store.get_checklist_review("manual:yc-001")["profile"], "building")
            self.assertIsNone(store.get_checklist_review("manual:none"))

    def test_all_checklist_reviews(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            store.save_checklist_review("a:1", {"profile": "building", "auto": {}, "manual": {}})
            store.save_checklist_review("b:2", {"profile": "land", "auto": {}, "manual": {}})
            self.assertEqual(set(store.all_checklist_reviews()), {"a:1", "b:2"})

    def test_ledger_delete_cascades_to_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = ListingStore(Path(temp_dir) / "seen.sqlite3")
            store.upsert_ledger_entry("a:1", {"title": "x"})
            store.save_checklist_review("a:1", {"profile": "building", "auto": {}, "manual": {}})
            store.delete_ledger_entry("a:1")
            self.assertIsNone(store.get_checklist_review("a:1"))
```

- [ ] **Step 2: 실패 확인** → AttributeError(save_checklist_review)
- [ ] **Step 3: 구현** — `initialize()`에 테이블 추가, `save_checklist_review`(upsert), `get_checklist_review`, `all_checklist_reviews`, `delete_checklist_review` 메서드. `delete_ledger_entry`에서 같은 트랜잭션으로 검토 삭제.

```sql
CREATE TABLE IF NOT EXISTS checklist_reviews (
    identity TEXT PRIMARY KEY,
    review_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
```

- [ ] **Step 4: 통과 확인** — `python -m pytest tests/test_store.py -q`

### Task 5: web_server.py — 체크리스트 API + first_seen_at

**Files:**
- Modify: `realestate_alert/web_server.py`
- Test: `tests/test_web_server.py`

- [ ] **Step 1: 실패하는 테스트 추가** (기존 `_write_fixture_config`/`_start_server`/`_request_json` 헬퍼 재사용)

```python
class ChecklistApiTests(unittest.TestCase):
    def test_definition_endpoint(self):
        # GET /api/checklist/definition → profiles + items
        ...
        self.assertIn("building", response["profiles"])
        self.assertTrue(any(item["item_id"] == "road_access" for item in response["items"]))

    def test_evaluate_and_manual_flow(self):
        # 1) POST /api/checklist/evaluate (키 없는 환경 → auto 대부분 unknown, listing.zoning으로 zoning은 pass)
        # 2) POST /api/checklist/manual 로 loc_overall pass 체크
        # 3) GET /api/checklist/reviews 에 등급 요약 반영
        # 4) GET /api/checklist/review?identity=... 에 전체 항목 반환
        payload = {
            "identity": "manual:match",
            "listing": {"title": "후보", "location": "서울 양천구 목동 917-9", "zoning": "준주거지역"},
            "profile": "rebuild",
        }
        evaluated = _request_json(server, "POST", "/api/checklist/evaluate", payload)
        self.assertEqual(evaluated["review"]["profile"], "rebuild")
        zoning = next(i for i in evaluated["review"]["items"] if i["item_id"] == "zoning")
        self.assertEqual(zoning["status"], "pass")
        manual = _request_json(server, "POST", "/api/checklist/manual", {
            "identity": "manual:match", "item_id": "loc_overall", "status": "pass", "memo": "입지 양호",
        })
        self.assertGreaterEqual(manual["review"]["progress"]["manual_done"], 1)
        reviews = _request_json(server, "GET", "/api/checklist/reviews")
        self.assertIn("manual:match", reviews["reviews"])

    def test_manual_rejects_bad_status_and_item(self):
        # status="maybe" → 400, item_id="nope" → 400 (AssertionError로 확인)

    def test_listings_include_first_seen_at(self):
        # /api/scan 후 /api/listings → listings[0]["first_seen_at"] 존재
```

- [ ] **Step 2: 실패 확인** → 404 (AssertionError)
- [ ] **Step 3: 구현**
  - `do_GET`: `/api/checklist/definition` → `definition_payload()`. `/api/checklist/reviews` → 저장된 전체를 `compute_review`로 요약(grade/score/no_go/progress/profile). `/api/checklist/review?identity=` → 전체 계산 결과 또는 `{"review": None}`.
  - `do_POST`: `/api/checklist/evaluate` — identity/listing/profile 검증 → `verify_address(listing["location"])` → `evaluate_auto_items` → 기존 manual 보존 병합 저장 → `compute_review` 반환(+report errors). `/api/checklist/manual` — identity/item_id/status 검증(MANUAL_STATUSES, 항목 존재), 선택적 profile 갱신 → 저장 → 계산 반환.
  - `_listing_to_dict`에 `first_seen_at` 파라미터 추가, `_listings_payload`에서 전달.
  - `/api/ledger/delete`는 store cascade로 자동 처리(Task 4).
- [ ] **Step 4: 통과 확인** — `python -m pytest tests/test_web_server.py -q` 그리고 전체 `python -m pytest tests/ -q`

### Task 6: 프런트 — 신규 매물 강조

**Files:**
- Modify: `web/index.html` (topbar 아래 배너), `web/app.js`, `web/styles.css`

- [ ] **Step 1: index.html** — topbar 다음에 `#newBanner` 섹션(아이콘 + `#newBannerTitle` + `#newBannerSources` + "신규만 보기" 버튼, 기본 `hidden`).
- [ ] **Step 2: app.js** — `renderNewBanner()`(소스별 카운트, `sourceLabel`), `relativeTimeFrom(first_seen_at)`(UTC 파싱 → "N시간 전 등록"), `isFresh24h`, `sortNewFirst()`를 `renderBoard`에 적용, 카드에 NEW 배지 fresh 클래스 + 경과시간, 배너 버튼 → `setBoardFilter("new")`. `renderDashboard()`에서 `renderNewBanner()` 호출.
- [ ] **Step 3: styles.css** — `.new-banner`(레이어 글로우 + 시차), `.badge-new.fresh` 펄스 keyframes, `.new-ago` 작은 텍스트. `prefers-reduced-motion` 가드.
- [ ] **Step 4: 검증** — `python -m realestate_alert serve-web` 후 Playwright로 배너·정렬·배지 확인.

### Task 7: 프런트 — 필수조건 검색

**Files:**
- Modify: `web/index.html` (보드 필터 칩 + 모달 프리셋), `web/app.js`, `web/styles.css`

- [ ] **Step 1: index.html** — 보드 툴바에 `data-board-filter="fit"` 칩(`#countFit`), criteria 모달 상단에 프리셋 버튼 2개(`#presetBuildingButton`, `#presetLandButton`).
- [ ] **Step 2: app.js**
  - `triCheck(label, value, predicate)` — 값 없으면 `unknown`, 아니면 ok/fail.
  - `evaluateRequiredFit(listing)` — 토지: 대지·용도지역·접도 / 건물: 대지·연면적·주차·층수(+승강기 필수 시) → `{group: "met"|"unknown"|"fail", checks}`.
  - `renderBoard()`에 fit 모드 분기: 수집 전체를 3그룹으로 묶어 그룹 헤더(✅ 충족 N / ❓ 확인 필요 N — `<details>` 접기 / 미달 N — `<details>`)와 함께 렌더. `#countFit`은 충족 수.
  - 프리셋: `CRITERIA_PRESETS.building`(대지 496㎡=150평, 연면적 1983㎡=600평, 주차 13대, 승강기 필수), `CRITERIA_PRESETS.land`(대지 496㎡, 접도 6m). 버튼 클릭 → 모달 입력값 채움.
  - `assetCriteria`를 `rea210:assetCriteria` localStorage에 저장/복원.
- [ ] **Step 3: styles.css** — `.fit-group-head`, `.fit-check-chips`(카드에 미충족 항목 표시), details 스타일.
- [ ] **Step 4: 검증** — 정적 모드(샘플 3건)에서 그룹 분류 확인 + Playwright.

### Task 8: 프런트 — 체크리스트 검토 모달 + 매물장 배지 + 3D

**Files:**
- Modify: `web/index.html` (매물장 검토 열 + `#checklistModal`), `web/app.js`, `web/styles.css`

- [ ] **Step 1: index.html** — 매물장 테이블 헤더에 "검토" 열 추가. `#checklistModal` dialog: 헤더(제목+매물명 `#checklistSubtitle`+닫기), 헤드라인(등급 배지 `#checklistGrade` / 점수 `#checklistScore` / 진행률 `#checklistProgress` / 프로필 select `#checklistProfile` / "자동 검증 실행" `#checklistEvaluateButton`), 본문 `#checklistSections`.
- [ ] **Step 2: app.js**
  - state 확장: `checklist: {definition: null, reviews: new Map(), current: null, currentIdentity: null}`.
  - 부트 시 `loadChecklistData()` (definition + reviews, 서버 모드만).
  - `renderLedger()` 행에 등급 배지(`gradeBadgeHtml`) + "체크리스트" 버튼 → `openChecklistModal(identity)`.
  - `openChecklistModal`: `/api/checklist/review?identity=` 로드 → `renderChecklistModal()` → `showModal()`.
  - `renderChecklistModal()`: current 없으면 definition에서 프로필별 빈 항목 구성. 카테고리(CATEGORY_ORDER 순) 섹션 렌더 — auto: 판정 필(적합 ok/경고 need/부적합 risk/미확인 neutral) + evidence. info: evidence + 수동 확정 버튼. manual: 적합/부적합/해당없음 3버튼 + 메모 input(디바운스 저장).
  - `runChecklistEvaluate()`: POST evaluate → current 갱신 → reviews 재로드 → 등급 플립 애니메이션 + 매물장 재렌더. report errors 있으면 토스트 안내.
  - `setManualStatus(itemId, status)` / 메모 저장: POST manual(현재 profile 포함) → current 갱신.
  - `setGradeBadge(grade, animate)`: reflow 트릭으로 `grade-flip` 클래스 재적용.
- [ ] **Step 3: styles.css** — 3D 인터랙션 일괄:
  - `.grade-badge`(grade-a 초록/b 파랑/c 황색/d 회색/x 빨강/none 중립) + `@keyframes gradeFlip`(rotateY 90→0).
  - `.checklist-modal .modal-panel` 깊이 진입 `@keyframes modalDepth`(perspective translateZ(-160px)→0).
  - `.checklist-section` translateZ 계층, 항목 행 hover 부상.
  - 버튼 active translateZ 하강(전역 .button에 적용).
  - 전부 `prefers-reduced-motion: reduce`에서 비활성.
- [ ] **Step 4: 검증** — 전체 테스트 + serve-web + Playwright로 모달 열기/프로필 전환/수동 체크/등급 표시 확인.

### Task 9: 최종 검증

- [ ] `python -m pytest tests/ -q` 전체 통과
- [ ] `python -m realestate_alert serve-web --port 8770` 실행 (8765 점용 주의 — 메모리: serve-web 포트 중복 바인딩 함정)
- [ ] Playwright: ① 신규 배너 표시 ② 필수조건 칩 → 3그룹 ③ 매물장 추가 → 체크리스트 모달 → 자동 검증(키 없으면 미확인 처리 확인) → 수동 체크 → 등급 변동 ④ reduced-motion 외 3D 동작
- [ ] README에 새 기능 3줄 요약 추가
