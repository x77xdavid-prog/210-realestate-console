"""병원추천 복합 점수(recommend.py) 단위 테스트.

순수 함수: 가용 신호만 가중·정규화(누락 신호는 패널티 없음), 정형외과 가중 프로필.
"""

import unittest

from realestate_alert.models import Listing
from realestate_alert.recommend import (
    WEIGHTS,
    baseline_score,
    composite_score,
    enriched_score,
    extract_recommend_signals,
)


def _listing(**kwargs):
    base = dict(
        source="court",
        external_id="1",
        title="매물",
        location="서울특별시 양천구 목동 1",
        deposit=0,
        monthly_rent=0,
        area_m2=100.0,
        floor=None,
        premium=None,
        url="https://example.test/1",
        property_type="building",
        usage="근린생활시설",
    )
    base.update(kwargs)
    return Listing(**base)


_OPEN_FIT = {"level": "open", "label": "개원 가능", "reason": "", "fit_score": 80}
_CHECK_FIT = {"level": "check", "label": "확인 필요", "reason": "", "fit_score": 35}


class CompositeScoreTests(unittest.TestCase):
    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(WEIGHTS["ortho"].values()), 1.0, places=9)

    def test_single_signal_full(self):
        self.assertEqual(composite_score({"fit": 1.0}, profile="ortho"), 100.0)

    def test_missing_signals_are_not_penalized(self):
        # fit=1.0(가중0.30), grade=0.0(가중0.20) → (0.30)/(0.50)*100 = 60.0
        self.assertEqual(composite_score({"fit": 1.0, "grade": 0.0}, profile="ortho"), 60.0)

    def test_empty_signals_zero(self):
        self.assertEqual(composite_score({}, profile="ortho"), 0.0)

    def test_subscores_clamped(self):
        self.assertEqual(composite_score({"fit": 2.0}, profile="ortho"), 100.0)
        self.assertEqual(composite_score({"fit": -1.0}, profile="ortho"), 0.0)


class BaselineScoreTests(unittest.TestCase):
    def test_open_beats_check(self):
        open_s = baseline_score(_listing(), _OPEN_FIT)
        check_s = baseline_score(_listing(), _CHECK_FIT)
        self.assertGreater(open_s, check_s)

    def test_more_discount_raises_score(self):
        low = baseline_score(_listing(appraisal_price=1000, min_bid_price=900), _OPEN_FIT)
        high = baseline_score(_listing(appraisal_price=1000, min_bid_price=500), _OPEN_FIT)
        self.assertGreater(high, low)

    def test_baseline_ignores_competition_and_grade(self):
        # 베이스라인은 경쟁의원·등급·시세 신호를 쓰지 않는다(무료 신호만).
        score = baseline_score(_listing(), _OPEN_FIT)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)


class EnrichedScoreTests(unittest.TestCase):
    def test_low_competition_beats_high(self):
        few = enriched_score(_listing(), _OPEN_FIT, grade="B", ortho_count=0)
        many = enriched_score(_listing(), _OPEN_FIT, grade="B", ortho_count=5)
        self.assertGreater(few, many)

    def test_cheaper_than_market_beats_expensive(self):
        cheap = enriched_score(_listing(min_bid_price=80_000, area_m2=1.0), _OPEN_FIT,
                               grade="B", market_avg_ppm=100_000)
        pricey = enriched_score(_listing(min_bid_price=140_000, area_m2=1.0), _OPEN_FIT,
                                grade="B", market_avg_ppm=100_000)
        self.assertGreater(cheap, pricey)

    def test_grade_a_beats_unfit_grade(self):
        a = enriched_score(_listing(), _OPEN_FIT, grade="A", ortho_count=1)
        bad = enriched_score(_listing(), _OPEN_FIT, grade="부적합", ortho_count=1)
        self.assertGreater(a, bad)

    def test_enriched_uses_more_signals_than_baseline(self):
        # 경쟁 0·등급 A 가 붙으면 베이스라인보다 점수가 달라진다(보통 상승).
        base = baseline_score(_listing(), _OPEN_FIT)
        rich = enriched_score(_listing(), _OPEN_FIT, grade="A", ortho_count=0)
        self.assertNotEqual(base, rich)


class ExtractSignalsTests(unittest.TestCase):
    def test_extracts_all_fields(self):
        report = {
            "market": {"avg_price_per_m2": 12345.0},
            "medical": {"ortho_clinic_count": 2, "pharmacy_count": 5},
            "building": {"main_purpose": "제2종근린생활시설"},
            "land": {"zoning_names": ["일반상업지역", "방화지구"]},
        }
        sig = extract_recommend_signals(report)
        self.assertEqual(sig["market_avg_ppm"], 12345.0)
        self.assertEqual(sig["ortho_count"], 2)
        self.assertEqual(sig["main_purpose"], "제2종근린생활시설")
        self.assertEqual(sig["zoning"], "일반상업지역, 방화지구")

    def test_missing_sections_yield_none(self):
        sig = extract_recommend_signals({})
        self.assertIsNone(sig["market_avg_ppm"])
        self.assertIsNone(sig["ortho_count"])
        self.assertIsNone(sig["main_purpose"])
        self.assertIsNone(sig["zoning"])


if __name__ == "__main__":
    unittest.main()
