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
