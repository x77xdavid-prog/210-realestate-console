import unittest
from realestate_alert.models import AuctionDetail, Photo, StatusItem, BidEvent, Listing


class ModelDetailTests(unittest.TestCase):
    def test_auction_detail_holds_rich_fields(self):
        d = AuctionDetail(
            identity="court:2024타경58264-1", court="서울서부지방법원", dept="경매7계",
            case_no="2024타경58264", addr_road="서울 마포구 만리재옛2길 14",
            addr_jibun="서울 마포구 신공덕동 5-38", usage="다세대", auction_type="강제경매",
            land_m2=44.01, bldg_m2=51.14, appraisal=594000000, min_bid=32656000,
            deposit=3265600, claim_amt=563644488, fail_count=13, sale_date="20260623",
            photos=(Photo("court:x/01.jpg", "외관", 1),),
            status_items=(StatusItem("위치 및 주위환경", "공덕역 인근"),),
            bid_history=(BidEvent("20260519", 40820000, "유찰"),),
            incumbrances=("임차권등기 보증금 5.3억 인수",),
            doc_ecid="ECID123", latitude=37.5, longitude=126.9,
        )
        self.assertEqual(d.fail_count, 13)
        self.assertEqual(d.photos[0].seq, 1)
        self.assertEqual(d.bid_history[0].result, "유찰")

    def test_listing_card_fields_default_empty(self):
        l = Listing(source="court", external_id="x", title="t", location="l",
                    deposit=0, monthly_rent=0, area_m2=0.0, floor=None, premium=None, url="u")
        self.assertIsNone(l.thumbnail_path)
        self.assertEqual(l.incumbrance_tags, ())
