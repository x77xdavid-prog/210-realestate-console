import json
import unittest

from realestate_alert.court_auction import (
    COURT_CODES,
    CourtAuctionSource,
    build_search_body,
)


def _result(items: list[dict]) -> str:
    return json.dumps(
        {
            "status": 200,
            "data": {
                "dma_pageInfo": {"totalCnt": str(len(items))},
                "dlt_srchResult": items,
            },
        },
        ensure_ascii=False,
    )


SAMPLE_ITEMS = [
    {
        "srnSaNo": "2024타경1009",
        "maemulSer": "1",
        "dspslUsgNm": "근린생활시설",
        "hjguSido": "서울특별시",
        "hjguSigu": "양천구",
        "hjguDong": "목동",
        "daepyoLotno": "917-9",
        "minmaePrice": "1100000000",
        "gamevalAmt": "1456760000",
        "yuchalCnt": "2",
        "maeGiil": "20260701",
        "pjbBuldList": "철근콘크리트조 900㎡",
        "jiwonNm": "서울남부지방법원",
        "jpDeptNm": "경매7계",
        "boCd": "B000212",
        "wgs84Xcordi": "126.85",
        "wgs84Ycordi": "37.52",
        "maxArea": "900",
    },
    {  # 같은 사건·물건 회차 중복 → 1건으로
        "srnSaNo": "2024타경1009",
        "maemulSer": "1",
        "dspslUsgNm": "근린생활시설",
        "hjguSido": "서울특별시",
        "hjguSigu": "양천구",
        "hjguDong": "목동",
        "daepyoLotno": "917-9",
        "minmaePrice": "1200000000",
        "gamevalAmt": "1456760000",
        "yuchalCnt": "1",
        "maeGiil": "20260801",
        "jiwonNm": "서울남부지방법원",
    },
    {  # 타겟 구 아님 → 제외
        "srnSaNo": "2024타경2000",
        "maemulSer": "1",
        "dspslUsgNm": "아파트",
        "hjguSido": "서울특별시",
        "hjguSigu": "금천구",
        "hjguDong": "시흥동",
        "daepyoLotno": "100",
        "minmaePrice": "500000000",
        "gamevalAmt": "500000000",
        "yuchalCnt": "0",
        "jiwonNm": "서울남부지방법원",
    },
]


class CourtAuctionTests(unittest.TestCase):
    def test_court_code_mapping_known(self):
        self.assertEqual(COURT_CODES["서울남부지방법원"], "B000212")

    def test_build_body_sets_court_and_dates(self):
        body = build_search_body(court_code="B000212", begin_ymd="20260612", end_ymd="20260710", page_size=40)
        info = body["dma_srchGdsDtlSrchInfo"]
        self.assertEqual(info["cortOfcCd"], "B000212")
        self.assertEqual(info["bidBgngYmd"], "20260612")
        self.assertEqual(info["bidEndYmd"], "20260710")
        self.assertEqual(body["dma_pageInfo"]["pageSize"], 40)

    def test_fetch_filters_target_districts_and_dedupes(self):
        source = CourtAuctionSource(
            court_code="B000212",
            target_districts=("양천구", "강서구", "구로구", "영등포구"),
            begin_ymd="20260612",
            end_ymd="20260710",
            fetcher=lambda body: _result(SAMPLE_ITEMS),
        )
        listings = source.fetch()

        self.assertEqual(len(listings), 1)  # 금천구 제외 + 회차 중복 제거
        listing = listings[0]
        self.assertEqual(listing.source, "court")
        self.assertEqual(listing.external_id, "2024타경1009-1")
        self.assertIn("[경매]", listing.title)
        self.assertIn("근린생활시설", listing.title)
        self.assertEqual(listing.location, "서울특별시 양천구 목동 917-9")
        self.assertEqual(listing.deposit, 1100000000)  # 최저매각가
        self.assertIn("감정가", listing.buildable_note)
        self.assertIn("유찰 2회", listing.buildable_note)
        # A2 구조화 필드 — 할인율%·D-day·유찰 표시에 사용
        self.assertEqual(listing.appraisal_price, 1456760000)
        self.assertEqual(listing.min_bid_price, 1100000000)
        self.assertEqual(listing.fail_count, 2)
        self.assertEqual(listing.sale_date, "20260701")

    def test_fetch_handles_empty_and_error(self):
        empty = CourtAuctionSource(fetcher=lambda body: _result([]))
        self.assertEqual(empty.fetch(), [])

        def boom(body):
            raise RuntimeError("network down")

        broken = CourtAuctionSource(fetcher=boom)
        self.assertEqual(broken.fetch(), [])  # 실패해도 빈 목록 (다른 소스 진행)

    def test_fetch_captures_detail_keys(self):
        source = CourtAuctionSource(
            court_code="B000212", begin_ymd="20260612", end_ymd="20260710",
            fetcher=lambda body: _result(SAMPLE_ITEMS),
        )
        listing = source.fetch()[0]
        self.assertEqual(listing.cs_no, "2024타경1009")
        self.assertEqual(listing.cort_ofc_cd, "B000212")
        self.assertEqual(listing.gds_seq, "1")
        self.assertAlmostEqual(listing.latitude, 37.52, places=2)


if __name__ == "__main__":
    unittest.main()
