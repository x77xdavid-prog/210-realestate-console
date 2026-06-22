import unittest

from realestate_alert.court_sale_spec import (
    fetch_sale_spec,
    parse_sale_spec,
    reconstruct_lines,
)

# 실제 매각물건명세서 재구성 라인 구조를 모사한 합성 픽스처 (가명)
SAMPLE_LINES = [
    "서 울 중 앙 지 방 법 원",
    "매각물건명세서",
    "2024타경12345 부동산임의경매",
    "지 토지 : 2003.05.23. 근",
    "별지 기재와 같음 저당권 배당요구종기 2008. 11. 28.",
    "집합건물 : 2008.07.09 근",
    "부동산의 점유자와 점유의 권원, 점유할 수 있는 기간, 차임 또는 보증금",
    "성  명 부분 구 분 권 원 (점유기간)",
    "록 신청일자",
    "홍길동 102호 권리신고 2008.03.02.~ 천만원 30만원 2005.07.18 미상 2008.10.23.",
    "임차인",
    "김영수 현황조사 2016.10.20.",
    "임차인",
    "<비고>",
    "홍길동:2005.3.2.자로 김철수와 계약",
    "김영수:홍길동의 배우자임",
    "※ 최선순위 설정일자보다 대항요건을 먼저 갖춘 주택 임차인의",
    "수 있고, 대항력과 우선변제권이 있는 주택 임차인이",
    "부동산의 표시",
    "2024타경12345",
]


class ParseSaleSpecTests(unittest.TestCase):
    def setUp(self):
        self.r = parse_sale_spec(SAMPLE_LINES)

    def test_dividend_deadline(self):
        self.assertEqual(self.r["dividend_deadline"], "2008.11.28")

    def test_priority_dates(self):
        self.assertIn("토지 2003.05.23", self.r["priority"])
        self.assertIn("집합건물 2008.07.09", self.r["priority"])

    def test_tenants_extracted(self):
        names = [t["name"] for t in self.r["tenants"]]
        self.assertEqual(names, ["홍길동", "김영수"])
        # 첫 임차인 행에 보증금/차임/전입/배당요구 데이터가 실린다
        self.assertIn("천만원", self.r["tenants"][0]["detail"])
        self.assertIn("2008.10.23", self.r["tenants"][0]["detail"])

    def test_notes_keep_specific_drop_boilerplate(self):
        joined = " ".join(self.r["notes"])
        self.assertIn("홍길동:2005.3.2", joined)
        self.assertIn("배우자", joined)
        self.assertNotIn("대항력과 우선변제권", joined)  # 보일러플레이트 제외
        self.assertNotIn("최선순위 설정일자보다", joined)

    def test_has_data(self):
        self.assertTrue(self.r["has_data"])

    def test_empty_lines(self):
        r = parse_sale_spec([])
        self.assertFalse(r["has_data"])
        self.assertEqual(r["tenants"], [])
        self.assertIsNone(r["dividend_deadline"])


class ReconstructLinesTests(unittest.TestCase):
    def test_groups_by_y_and_sorts_by_x(self):
        runs = [
            {"text": "건", "rect": [{"top": 700, "left": 50}]},
            {"text": "물", "rect": [{"top": 700, "left": 60}]},  # 같은 줄(top 동일)
            {"text": "위", "rect": [{"top": 600, "left": 30}]},  # 아래 줄(top 작음)
            {"text": "아래", "rect": [{"top": 600, "left": 80}]},
        ]
        lines = reconstruct_lines(runs)
        self.assertEqual(lines[0], "건물")  # 위 줄(top 큼) 먼저, x정렬
        self.assertEqual(lines[1], "위아래")

    def test_skips_runs_without_rect(self):
        self.assertEqual(reconstruct_lines([{"text": "x", "rect": []}]), [])


class FetchSaleSpecTests(unittest.TestCase):
    def test_injected_lines_fetcher(self):
        r = fetch_sale_spec("c", "B000210", "1", lines_fetcher=lambda a, b, c: SAMPLE_LINES)
        self.assertEqual(r["dividend_deadline"], "2008.11.28")
        self.assertEqual(len(r["tenants"]), 2)

    def test_fetcher_error_absorbed(self):
        def boom(a, b, c):
            raise RuntimeError("network down")

        r = fetch_sale_spec("c", "o", "1", lines_fetcher=boom)
        self.assertFalse(r["has_data"])
        self.assertEqual(r["tenants"], [])


if __name__ == "__main__":
    unittest.main()
