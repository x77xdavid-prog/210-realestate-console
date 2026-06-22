# tests/test_court_auction_detail.py
import unittest
from realestate_alert.court_auction_detail import (
    parse_detail, status_label, bid_result, extract_incumbrance_tags,
)

PAYLOAD = {"data": {"dma_result": {
    "csBaseInfo": {"cortOfcNm": "서울서부지방법원", "csNo": "2024타경58264",
                   "userCsNo": "2024타경58264", "clmAmt": "563644488"},
    "dspslGdsDxdyInfo": {"aeeEvlAmt": "594000000", "fstPbancLwsDspslPrc": "32656000",
        "flbdNcnt": "13", "dspslDxdyYmd": "20260623", "cortSptNm": "경매7계",
        "ndstrcRghCtt": "을구 5번 임차권등기(보증금 530,000,000원) 매수인 인수. 갑구 7번 가등기 인수.",
        "realMulKind": "다세대"},
    "gdsDspslObjctLst": [{"userPrintSt": "서울 마포구 만리재옛2길 14", "rprsLtnoAddr": "서울 마포구 신공덕동 5-38",
        "bldDtlDts": "5층501호", "stXcrd": "126.9", "stYcrd": "37.5"}],
    "csPicLst": [{"cortAuctnPicSeq": "1", "cortAuctnPicDvsCd": "000241", "picTitlNm": "a.jpg"}],
    "gdsDspslDxdyLst": [
        {"dxdyYmd": "20260519", "tsLwsDspslPrc": 40820000, "auctnDxdyRsltCd": "002", "auctnDxdyKndCd": "01"},
        {"dxdyYmd": "20260623", "tsLwsDspslPrc": 32656000, "auctnDxdyRsltCd": None, "auctnDxdyKndCd": "01"},
        {"dxdyYmd": "20260630", "tsLwsDspslPrc": 0, "auctnDxdyRsltCd": None, "auctnDxdyKndCd": "02"}],
    "aeeWevlMnpntLst": [{"aeeWevlMnpntItmCd": "00083001", "aeeWevlMnpntCtt": "공덕역 인근"}],
}}}


class DetailParseTests(unittest.TestCase):
    def test_status_label_maps_code(self):
        self.assertEqual(status_label("00083011"), "토지이용계획 및 제한상태")

    def test_bid_result_maps(self):
        self.assertEqual(bid_result("002", "01"), "유찰")
        self.assertEqual(bid_result(None, "01"), "진행")
        self.assertEqual(bid_result(None, "02"), "매각결정")

    def test_incumbrance_tags_extracted(self):
        tags = extract_incumbrance_tags("을구 임차권등기 ... 갑구 가등기 인수 ... 선순위")
        self.assertIn("임차권등기", tags)
        self.assertIn("선순위가등기", tags)

    def test_parse_detail_builds_auction_detail(self):
        d = parse_detail(PAYLOAD, "court:2024타경58264-1", {1: "court:x/01.jpg"})
        self.assertEqual(d.appraisal, 594000000)
        self.assertEqual(d.fail_count, 13)
        self.assertEqual(d.usage, "다세대")
        self.assertEqual(len(d.bid_history), 3)
        self.assertEqual(d.bid_history[1].result, "진행")
        self.assertEqual(d.status_items[0].label, "위치 및 주위환경")
        self.assertEqual(d.photos[0].file, "court:x/01.jpg")
        self.assertIn("임차권등기", d.incumbrances[0])
