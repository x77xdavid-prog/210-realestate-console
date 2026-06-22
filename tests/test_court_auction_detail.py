# tests/test_court_auction_detail.py
import unittest
from realestate_alert.court_auction_detail import (
    parse_detail, status_label, bid_result, extract_incumbrance_tags,
)

SUBLIST_PAYLOAD = {"data": {"dma_result": {
    "csBaseInfo": {"cortOfcNm": "서울남부지방법원", "csNo": "20250130000596",
                   "userCsNo": "2025타경596", "clmAmt": 3182184540},
    "dspslGdsDxdyInfo": {
        "aeeEvlAmt": 1146719360, "fstPbancLwsDspslPrc": 1146719360,
        "flbdNcnt": 0, "dspslDxdyYmd": "20260623", "cortSptNm": "경매10계",
        "ndstrcRghCtt": "", "realMulKind": "1",
        "dspslGdsRmk": "일괄매각. 제시외 건물 포함",
    },
    "gdsDspslObjctLst": [{"userPrintSt": "서울 영등포구 여의대방로59길 40-2",
                           "rprsLtnoAddr": "서울 영등포구 신길동 7-31",
                           "stXcrd": "126.9", "stYcrd": "37.5"}],
    "gdsDspslDxdyLst": [],
    "aeeWevlMnpntLst": [],
    "dstrtDemnInfo": [{"orddcsDvsCd": "021", "dstrtDemnLstprdYmd": "20251015"}],
    "gdsNotSugtBldLsstAll": [
        [{"etcUsgCtt": "주택일부", "bldStrcDts": "세맨블록조 및 판넬조",
          "bldArDts": "56㎡", "evlAmt": 4800000, "sugtBsdsBldRmk": "관찰감가"}],
        [],
    ],
    "bldSdtrDtlLstAll": [
        [{"rletDvsDts": "일반건물", "bldSdtrDtlDts": "목조기와지붕단층주택\n43.97㎡ "}],
    ],
    "gdsRletStLtnoLstAll": [
        [{"rletStLtnoAddr": "7-31", "adongSdNm": "서울특별시",
          "adongSggNm": "영등포구", "adongEmdNm": "신길동",
          "rdnm": "여의대방로59길", "rdnmBldNo": "40-2",
          "auctnLstDvsCd": "02"}],
    ],
}}}

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


class SublistParseTests(unittest.TestCase):
    def setUp(self):
        self.d = parse_detail(SUBLIST_PAYLOAD, "court:2025타경596-1", {})

    def test_presented_outside_parsed(self):
        self.assertEqual(len(self.d.presented_outside), 1)
        item = self.d.presented_outside[0]
        self.assertEqual(item["usage"], "주택일부")
        self.assertEqual(item["structure"], "세맨블록조 및 판넬조")
        self.assertEqual(item["area"], "56㎡")
        self.assertEqual(item["appraisal"], 4800000)
        self.assertEqual(item["note"], "관찰감가")

    def test_building_detail_parsed(self):
        self.assertEqual(len(self.d.building_detail), 1)
        item = self.d.building_detail[0]
        self.assertEqual(item["kind"], "일반건물")
        self.assertIn("목조기와지붕", item["detail"])

    def test_jibun_list_parsed(self):
        self.assertEqual(len(self.d.jibun_list), 1)
        item = self.d.jibun_list[0]
        self.assertEqual(item["jibun"], "7-31")
        self.assertIn("영등포구", item["addr"])
        self.assertEqual(item["road"], "여의대방로59길 40-2")

    def test_dividend_deadline_parsed(self):
        self.assertEqual(self.d.dividend_deadline, "20251015")

    def test_sale_notice_parsed(self):
        self.assertEqual(self.d.sale_notice, "일괄매각. 제시외 건물 포함")
