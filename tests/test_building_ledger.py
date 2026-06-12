import unittest

from realestate_alert.address import parse_parcel_address
from realestate_alert.building_ledger import fetch_building_titles, primary_title

TITLE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item>
        <bldNm>목동메디컬빌딩</bldNm>
        <mainPurpsCdNm>제2종근린생활시설</mainPurpsCdNm>
        <platArea>242.5</platArea>
        <archArea>140.2</archArea>
        <totArea>386.4</totArea>
        <bcRat>52.3</bcRat>
        <vlRat>183.1</vlRat>
        <grndFlrCnt>5</grndFlrCnt>
        <ugrndFlrCnt>1</ugrndFlrCnt>
        <indrMechUtcnt>0</indrMechUtcnt>
        <oudrMechUtcnt>0</oudrMechUtcnt>
        <indrAutoUtcnt>3</indrAutoUtcnt>
        <oudrAutoUtcnt>1</oudrAutoUtcnt>
        <rideUseElvtCnt>1</rideUseElvtCnt>
        <emgenUseElvtCnt>0</emgenUseElvtCnt>
        <useAprDay>20080417</useAprDay>
      </item>
      <item>
        <bldNm>부속동</bldNm>
        <mainPurpsCdNm>창고</mainPurpsCdNm>
        <totArea>40.0</totArea>
        <grndFlrCnt>1</grndFlrCnt>
      </item>
    </items>
  </body>
</response>
"""


class BuildingLedgerTests(unittest.TestCase):
    def test_parses_title_info_fields(self):
        parcel = parse_parcel_address("서울 양천구 목동 917-9")
        captured = {}

        def fake_fetch(url):
            captured["url"] = url
            return TITLE_XML

        titles = fetch_building_titles(parcel, service_key="test-key", fetcher=fake_fetch)

        self.assertIn("sigunguCd=11470", captured["url"])
        self.assertIn("bjdongCd=10100", captured["url"])
        self.assertIn("bun=0917", captured["url"])
        self.assertIn("ji=0009", captured["url"])
        self.assertEqual(len(titles), 2)

        main = primary_title(titles)
        self.assertEqual(main.building_name, "목동메디컬빌딩")
        self.assertEqual(main.parking_spaces, 4)
        self.assertEqual(main.elevator_count, 1)
        self.assertTrue(main.has_elevator)
        self.assertEqual(main.approval_year, 2008)
        self.assertEqual(main.ground_floors, 5)
        self.assertAlmostEqual(main.building_coverage_ratio, 52.3)
        self.assertAlmostEqual(main.floor_area_ratio, 183.1)

    def test_primary_title_of_empty_list_is_none(self):
        self.assertIsNone(primary_title([]))
