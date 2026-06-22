import unittest

from realestate_alert.checklist import (
    CHECKLIST_ITEMS,
    PROFILES,
    compute_review,
    definition_payload,
    evaluate_auto_items,
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


class EvaluateAutoItemsTests(unittest.TestCase):
    def test_empty_report_yields_unknown(self):
        results = evaluate_auto_items({}, {"building": None, "land": None, "market": None})
        self.assertEqual(results["zoning"]["status"], "unknown")
        self.assertEqual(results["road_access"]["status"], "unknown")
        self.assertEqual(results["parking"]["status"], "unknown")
        self.assertEqual(results["price_market"]["status"], "unknown")

    def test_zoning_exclusive_residential_warns(self):
        report = {"land": {"zoning_names": ["제1종전용주거지역"]}}
        self.assertEqual(evaluate_auto_items({}, report)["zoning"]["status"], "warn")

    def test_zoning_falls_back_to_listing(self):
        results = evaluate_auto_items({"zoning": "준주거지역"}, {})
        self.assertEqual(results["zoning"]["status"], "pass")
        self.assertIn("준주거지역", results["zoning"]["evidence"])

    def test_blind_land_fails_road_access(self):
        report = {"land": {"road_side": "맹지"}}
        self.assertEqual(evaluate_auto_items({}, report)["road_access"]["status"], "fail")

    def test_road_access_pass_with_width_hint(self):
        report = {"land": {"road_side": "광대한면", "road_width_hint_m": 25}}
        result = evaluate_auto_items({}, report)["road_access"]
        self.assertEqual(result["status"], "pass")
        self.assertIn("25", result["evidence"])

    def test_elevator_fail_when_multistory_without_lift(self):
        report = {"building": {"elevator_count": 0, "ground_floors": 5}}
        self.assertEqual(evaluate_auto_items({}, report)["elevator"]["status"], "fail")

    def test_elevator_pass_when_present(self):
        report = {"building": {"elevator_count": 2, "ground_floors": 5}}
        self.assertEqual(evaluate_auto_items({}, report)["elevator"]["status"], "pass")

    def test_parking_pass_and_warn(self):
        ok = {"building": {"parking_spaces": 14, "total_area_m2": 2000}}
        short = {"building": {"parking_spaces": 5, "total_area_m2": 2000}}
        self.assertEqual(evaluate_auto_items({}, ok)["parking"]["status"], "pass")
        self.assertEqual(evaluate_auto_items({}, short)["parking"]["status"], "warn")

    def test_building_age_warns_after_30_years(self):
        report = {"building": {"approval_year": 1990}}
        results = evaluate_auto_items({}, report, now_year=2026)
        self.assertEqual(results["building_age"]["status"], "warn")

    def test_building_age_pass_when_recent(self):
        report = {"building": {"approval_year": 2015}}
        results = evaluate_auto_items({}, report, now_year=2026)
        self.assertEqual(results["building_age"]["status"], "pass")

    def test_rebuild_age_always_pass(self):
        results = evaluate_auto_items({}, {"building": {"approval_year": 1985}}, now_year=2026)
        self.assertEqual(results["rebuild_age_ok"]["status"], "pass")
        self.assertIn("철거", results["rebuild_age_ok"]["evidence"])

    def test_price_market_warns_on_premium(self):
        listing = {"deposit": 3_000_000_000, "monthly_rent": 0, "building_area_m2": 1000}
        report = {"market": {"avg_price_per_m2": 2_000_000}}
        self.assertEqual(evaluate_auto_items(listing, report)["price_market"]["status"], "warn")

    def test_price_market_pass_when_reasonable(self):
        listing = {"deposit": 2_000_000_000, "monthly_rent": 0, "building_area_m2": 1000}
        report = {"market": {"avg_price_per_m2": 2_000_000}}
        self.assertEqual(evaluate_auto_items(listing, report)["price_market"]["status"], "pass")

    def test_buildable_volume_info(self):
        report = {"building": {"plat_area_m2": 500}}
        result = evaluate_auto_items({"floor_area_ratio": 200}, report)["buildable_volume"]
        self.assertEqual(result["status"], "info")
        self.assertIn("1,000", result["evidence"])

    def test_land_price_basis_with_listing_price(self):
        listing = {"deposit": 1_000_000_000, "monthly_rent": 0}
        report = {
            "building": {"plat_area_m2": 500},
            "land": {"official_price_per_m2": 1_000_000, "official_price_year": 2025},
        }
        result = evaluate_auto_items(listing, report)["land_price_basis"]
        self.assertEqual(result["status"], "info")
        self.assertIn("2.0배", result["evidence"])

    def test_current_use_info(self):
        report = {"building": {"main_purpose": "제2종근린생활시설"}}
        result = evaluate_auto_items({}, report)["current_use"]
        self.assertEqual(result["status"], "info")
        self.assertIn("제2종근린생활시설", result["evidence"])

    def test_current_use_falls_back_to_listing(self):
        result = evaluate_auto_items({"main_purpose": "유흥주점/소매점/사무소"}, {})["current_use"]
        self.assertEqual(result["status"], "info")
        self.assertIn("유흥주점", result["evidence"])

    def test_competition_and_pharmacy_unknown_without_medical_data(self):
        results = evaluate_auto_items({}, {})
        self.assertEqual(results["loc_competition"]["status"], "unknown")
        self.assertEqual(results["loc_pharmacy"]["status"], "unknown")
        self.assertIn("활용신청", results["loc_competition"]["evidence"])

    def test_competition_pass_when_few_clinics(self):
        report = {"medical": {"ortho_clinic_count": 2, "ortho_clinic_names": ["a정형외과", "b정형외과"], "pharmacy_count": 3}}
        result = evaluate_auto_items({}, report)["loc_competition"]
        self.assertEqual(result["status"], "pass")
        self.assertIn("2곳", result["evidence"])

    def test_competition_warns_when_crowded(self):
        report = {"medical": {"ortho_clinic_count": 5, "ortho_clinic_names": ["a", "b", "c", "d", "e"], "pharmacy_count": 3}}
        result = evaluate_auto_items({}, report)["loc_competition"]
        self.assertEqual(result["status"], "warn")
        self.assertIn("경쟁 밀집", result["evidence"])

    def test_competition_shows_treating_count_context(self):
        # 정형외과 전문의원 17곳(직접 경쟁) + 정형외과 진료 의원 50곳(넓은 경쟁)을 함께 표시
        report = {"medical": {
            "ortho_clinic_count": 17,
            "ortho_clinic_names": ["a정형외과", "b정형외과", "c정형외과"],
            "pharmacy_count": 5,
            "ortho_treating_count": 50,
        }}
        result = evaluate_auto_items({}, report)["loc_competition"]
        self.assertEqual(result["status"], "warn")
        self.assertIn("정형외과 의원 17곳", result["evidence"])
        self.assertIn("정형외과 진료 의원 50곳", result["evidence"])

    def test_pharmacy_pass_and_warn(self):
        with_pharmacy = {"medical": {"ortho_clinic_count": 0, "ortho_clinic_names": [], "pharmacy_count": 4}}
        without_pharmacy = {"medical": {"ortho_clinic_count": 0, "ortho_clinic_names": [], "pharmacy_count": 0}}
        self.assertEqual(evaluate_auto_items({}, with_pharmacy)["loc_pharmacy"]["status"], "pass")
        self.assertEqual(evaluate_auto_items({}, without_pharmacy)["loc_pharmacy"]["status"], "warn")

    def test_competition_and_pharmacy_are_auto_items(self):
        kinds = {item.item_id: item.kind for item in CHECKLIST_ITEMS}
        self.assertEqual(kinds["loc_competition"], "auto")
        self.assertEqual(kinds["loc_pharmacy"], "auto")


class ComputeReviewTests(unittest.TestCase):
    def test_critical_fail_forces_no_go(self):
        auto = {"road_access": {"status": "fail", "evidence": "맹지"}}
        review = compute_review("land", auto, {})
        self.assertEqual(review["grade"], "부적합")
        self.assertTrue(review["no_go"])

    def test_critical_manual_fail_forces_no_go(self):
        manual = {"tenant_eviction": {"status": "fail", "memo": "명도 거부 임차인"}}
        review = compute_review("rebuild", {}, manual)
        self.assertEqual(review["grade"], "부적합")

    def test_all_pass_scores_grade_a(self):
        items = items_for_profile("land")
        auto = {i.item_id: {"status": "pass", "evidence": ""} for i in items if i.kind == "auto"}
        manual = {i.item_id: {"status": "pass", "memo": ""} for i in items if i.kind in ("manual", "info")}
        review = compute_review("land", auto, manual)
        self.assertEqual(review["grade"], "A")
        self.assertEqual(review["score"], 100.0)
        self.assertFalse(review["no_go"])

    def test_unchecked_and_unknown_excluded_from_score(self):
        review = compute_review("land", {"zoning": {"status": "pass", "evidence": ""}}, {})
        self.assertEqual(review["score"], 100.0)
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

    def test_na_excluded_from_score(self):
        manual = {
            "loc_overall": {"status": "pass", "memo": ""},
            "loc_pharmacy": {"status": "na", "memo": ""},
        }
        review = compute_review("land", {}, manual)
        self.assertEqual(review["score"], 100.0)

    def test_progress_counts(self):
        auto = {
            "zoning": {"status": "pass", "evidence": ""},
            "road_access": {"status": "unknown", "evidence": ""},
        }
        manual = {"loc_overall": {"status": "pass", "memo": ""}}
        review = compute_review("land", auto, manual)
        self.assertEqual(review["progress"]["auto_done"], 1)
        self.assertGreater(review["progress"]["auto_total"], 1)
        self.assertEqual(review["progress"]["manual_done"], 1)

    def test_items_include_definition_and_state(self):
        review = compute_review("building", {}, {"mri_load": {"status": "fail", "memo": "보강 불가"}})
        row = next(item for item in review["items"] if item["item_id"] == "mri_load")
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["memo"], "보강 불가")
        self.assertEqual(row["category"], "물리")

    def test_info_item_scored_by_manual_confirmation(self):
        auto = {"buildable_volume": {"status": "info", "evidence": "대지 500㎡ × 200%"}}
        manual = {"buildable_volume": {"status": "fail", "memo": "목표 연면적 미달"}}
        review = compute_review("land", auto, manual)
        row = next(item for item in review["items"] if item["item_id"] == "buildable_volume")
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["evidence"], "대지 500㎡ × 200%")
        self.assertEqual(review["score"], 0.0)

    def test_invalid_profile_raises(self):
        with self.assertRaises(ValueError):
            compute_review("hotel", {}, {})

    def test_override_fills_unknown_auto_item(self):
        # API가 못 채워 미확인이던 용도지역을 제공 자료로 적합 처리
        auto = {"zoning": {"status": "unknown", "evidence": "용도지역 정보 없음"}}
        override = {"zoning": {"status": "pass", "evidence": "일반상업지역 — 의원·병원 허용"}}
        review = compute_review("building", auto, {}, override)
        row = next(i for i in review["items"] if i["item_id"] == "zoning")
        self.assertEqual(row["status"], "pass")
        self.assertEqual(row["evidence"], "일반상업지역 — 의원·병원 허용")
        self.assertEqual(row["source"], "manual")

    def test_override_wins_over_api_result(self):
        auto = {"building_age": {"status": "unknown", "evidence": "준공년도 정보 없음"}}
        override = {"building_age": {"status": "warn", "evidence": "1983년 준공(약 43년)"}}
        review = compute_review("building", auto, {}, override)
        row = next(i for i in review["items"] if i["item_id"] == "building_age")
        self.assertEqual(row["status"], "warn")
        self.assertIn("1983", row["evidence"])

    def test_non_overridden_rows_report_auto_source(self):
        auto = {"zoning": {"status": "pass", "evidence": "준주거지역"}}
        review = compute_review("building", auto, {}, {})
        row = next(i for i in review["items"] if i["item_id"] == "zoning")
        self.assertEqual(row["source"], "auto")

    def test_override_evidence_on_info_item(self):
        # info 항목은 상태는 수동 체크로 확정하되, 근거(evidence)는 override로 채운다
        override = {"current_use": {"status": "info", "evidence": "B1·2·3F 유흥주점, 1F 소매점+1종근생, 4F 사무소"}}
        review = compute_review("building", {}, {}, override)
        row = next(i for i in review["items"] if i["item_id"] == "current_use")
        self.assertIn("유흥주점", row["evidence"])
        self.assertEqual(row["source"], "manual")

    def test_override_counts_toward_auto_progress(self):
        override = {"zoning": {"status": "pass", "evidence": "일반상업지역"}}
        review = compute_review("building", {}, {}, override)
        self.assertGreaterEqual(review["progress"]["auto_done"], 1)


if __name__ == "__main__":
    unittest.main()
