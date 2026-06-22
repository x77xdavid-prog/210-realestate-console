import unittest

from realestate_alert.hospital_fit import classify
from realestate_alert.models import Listing


def _listing(usage=None, property_type=None, title="매물", **kwargs):
    base = dict(
        source="court",
        external_id="1",
        title=title,
        location="서울특별시 양천구 목동 1",
        deposit=0,
        monthly_rent=0,
        area_m2=0.0,
        floor=None,
        premium=None,
        url="https://example.test/1",
        property_type=property_type,
        usage=usage,
    )
    base.update(kwargs)
    return Listing(**base)


class HospitalFitTests(unittest.TestCase):
    def test_commercial_building_is_open(self):
        for usage in ("상가용및업무용건물", "근린생활시설", "근린시설", "근린상가", "점포"):
            self.assertEqual(classify(_listing(usage=usage, property_type="building"))["level"], "open", usage)

    def test_vehicles_are_unfit(self):
        for usage in ("자동차", "차량", "선박"):
            self.assertEqual(classify(_listing(usage=usage, property_type="building"))["level"], "unfit", usage)

    def test_land_is_buildable(self):
        self.assertEqual(classify(_listing(usage="대지", property_type="land"))["level"], "build")
        self.assertEqual(classify(_listing(usage="토지", property_type="land"))["level"], "build")
        self.assertEqual(classify(_listing(usage="잡종지", property_type="land"))["level"], "build")

    def test_farmland_and_forest_are_unfit(self):
        for usage in ("전", "답", "임야", "과수원", "도로", "구거", "묘지"):
            self.assertEqual(classify(_listing(usage=usage, property_type="land"))["level"], "unfit", usage)

    def test_unfit_detected_from_title_parens(self):
        listing = _listing(usage="토지", property_type="land", title="[경매] 서울 강서구 (임야)")
        self.assertEqual(classify(listing)["level"], "unfit")

    def test_residential_is_check(self):
        for usage in ("주거용건물", "다세대", "아파트", "단독주택", "도시형생활주택"):
            self.assertEqual(classify(_listing(usage=usage, property_type="building"))["level"], "check", usage)

    def test_unknown_or_empty_is_check(self):
        self.assertEqual(classify(_listing(usage="기타", property_type="building"))["level"], "check")
        self.assertEqual(classify(_listing(usage=None, property_type="building"))["level"], "check")

    def test_lh_types(self):
        self.assertEqual(classify(_listing(usage="상가", property_type="building"))["level"], "open")
        self.assertEqual(classify(_listing(usage="토지", property_type="land"))["level"], "build")

    def test_result_has_label_and_reason(self):
        result = classify(_listing(usage="근린생활시설", property_type="building"))
        self.assertEqual(result["label"], "개원 가능")
        self.assertTrue(result["reason"])

    def test_commercial_takes_precedence_over_land_flag(self):
        # 상가 키워드가 있으면 토지 플래그보다 개원 가능 우선 (드물지만 방어적으로)
        listing = _listing(usage="근린상가", property_type="building", title="근린상가 1층")
        self.assertEqual(classify(listing)["level"], "open")


class HospitalFitScoreTests(unittest.TestCase):
    def test_result_has_fit_score_in_range(self):
        result = classify(_listing(usage="근린생활시설", property_type="building"))
        self.assertIn("fit_score", result)
        self.assertIsInstance(result["fit_score"], int)
        self.assertGreaterEqual(result["fit_score"], 0)
        self.assertLessEqual(result["fit_score"], 100)

    def test_fit_score_orders_by_level(self):
        open_s = classify(_listing(usage="근린생활시설", property_type="building"))["fit_score"]
        build_s = classify(_listing(usage="대지", property_type="land"))["fit_score"]
        check_s = classify(_listing(usage="단독주택", property_type="building"))["fit_score"]
        unfit_s = classify(_listing(usage="임야", property_type="land"))["fit_score"]
        self.assertGreater(open_s, build_s)
        self.assertGreater(build_s, check_s)
        self.assertGreater(check_s, unfit_s)


class HospitalFitPublicDataTests(unittest.TestCase):
    def test_main_purpose_commercial_is_open_even_without_usage(self):
        # 매물 용도가 비어도 건축물대장 주용도가 근린생활이면 개원 가능
        result = classify(_listing(usage=None, property_type="building"),
                          main_purpose="제2종근린생활시설")
        self.assertEqual(result["level"], "open")

    def test_main_purpose_medical_is_open(self):
        result = classify(_listing(usage=None), main_purpose="의료시설")
        self.assertEqual(result["level"], "open")

    def test_main_purpose_residential_is_check(self):
        result = classify(_listing(usage=None, property_type="building"),
                          main_purpose="단독주택")
        self.assertEqual(result["level"], "check")

    def test_commercial_zoning_scores_higher_than_exclusive_residential(self):
        # 같은 개원 가능 매물이라도 상업지역이 전용주거지역보다 점수가 높다
        commercial = classify(_listing(usage="근린생활시설", property_type="building"),
                              zoning="일반상업지역")["fit_score"]
        exclusive = classify(_listing(usage="근린생활시설", property_type="building"),
                             zoning="제1종전용주거지역")["fit_score"]
        self.assertGreater(commercial, exclusive)

    def test_keyword_variant_geunsaeng_is_open(self):
        # 용어 변이: "근생"·"1종근생"도 근린생활시설로 인식
        for usage in ("근생", "1종근생", "제2종근생"):
            self.assertEqual(classify(_listing(usage=usage, property_type="building"))["level"], "open", usage)

    def test_public_data_does_not_break_unfit(self):
        # 농지·임야는 주용도/용도지역이 있어도 부적합 유지
        result = classify(_listing(usage="임야", property_type="land"), zoning="자연녹지지역")
        self.assertEqual(result["level"], "unfit")

    def test_fit_score_stays_ordered_across_levels_with_public_data(self):
        # 공공데이터 보정이 적용돼도 레벨 간 점수 순서가 뒤집히지 않아야 한다.
        # check(가장 유리한 보정) < build(가장 불리한 보정) 인지 검증.
        check_best = classify(_listing(usage="단독주택", property_type="building"),
                              zoning="일반상업지역")["fit_score"]
        build_worst = classify(_listing(usage="대지", property_type="land"),
                               zoning="제1종전용주거지역")["fit_score"]
        self.assertGreater(build_worst, check_best)
        # open(가장 불리한 보정) > build(가장 유리한 보정)
        open_worst = classify(_listing(usage="근린생활시설", property_type="building"),
                              zoning="제1종전용주거지역")["fit_score"]
        build_best = classify(_listing(usage="대지", property_type="land"),
                              zoning="일반상업지역")["fit_score"]
        self.assertGreater(open_worst, build_best)
