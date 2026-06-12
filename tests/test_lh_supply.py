import json
import unittest

from realestate_alert.lh_supply import LhNoticeSource

LH_RESPONSE = json.dumps(
    [
        {"dsSch": [{"PAGE": "1"}]},
        {
            "dsList": [
                {
                    "PAN_ID": "BN-0001",
                    "PAN_NM": "마곡지구 의료시설용지 공급 공고",
                    "UPP_AIS_TP_CD": "01",
                    "UPP_AIS_TP_NM": "토지",
                    "CNP_CD_NM": "서울특별시",
                    "PAN_SS": "공고중",
                    "PAN_NT_ST_DT": "2026.06.01",
                    "CLSG_DT": "2026.07.01",
                    "DTL_URL": "https://apply.lh.or.kr/detail?panId=BN-0001",
                },
                {
                    "PAN_ID": "BN-0002",
                    "PAN_NM": "마감된 토지 공고",
                    "UPP_AIS_TP_CD": "01",
                    "UPP_AIS_TP_NM": "토지",
                    "CNP_CD_NM": "서울특별시",
                    "PAN_SS": "접수마감",
                    "PAN_NT_ST_DT": "2026.04.01",
                    "CLSG_DT": "2026.05.01",
                    "DTL_URL": "https://apply.lh.or.kr/detail?panId=BN-0002",
                },
            ],
            "resHeader": [{"SS_CODE": "Y"}],
        },
    ],
    ensure_ascii=False,
)

EMPTY_RESPONSE = json.dumps(
    [{"dsSch": [{}]}, {"dsList": [], "resHeader": [{"SS_CODE": "Y"}]}],
    ensure_ascii=False,
)


class LhNoticeSourceTests(unittest.TestCase):
    def test_fetch_maps_active_notices_only(self):
        calls = []

        def fake_fetcher(url: str) -> str:
            calls.append(url)
            return LH_RESPONSE if "UPP_AIS_TP_CD=01" in url else EMPTY_RESPONSE

        source = LhNoticeSource(service_key="test-key", fetcher=fake_fetcher)
        listings = source.fetch()

        self.assertEqual(len(calls), 2)  # 토지 + 상가 두 번 호출
        self.assertEqual(len(listings), 1)  # 접수마감 공고는 제외
        listing = listings[0]
        self.assertEqual(listing.source, "lh")
        self.assertEqual(listing.external_id, "BN-0001")
        self.assertIn("[LH 토지]", listing.title)
        self.assertIn("의료시설용지", listing.title)
        self.assertEqual(listing.property_type, "land")
        self.assertEqual(listing.url, "https://apply.lh.or.kr/detail?panId=BN-0001")
        self.assertIn("마감 2026.07.01", listing.buildable_note)

    def test_fetch_without_key_returns_empty(self):
        import os
        from unittest import mock

        clean_env = {k: v for k, v in os.environ.items() if k != "DATA_GO_KR_API_KEY"}
        with mock.patch.dict("os.environ", clean_env, clear=True):
            listings = LhNoticeSource().fetch()
        self.assertEqual(listings, [])


if __name__ == "__main__":
    unittest.main()
