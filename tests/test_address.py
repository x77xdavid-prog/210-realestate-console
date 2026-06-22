import unittest

from realestate_alert.address import extract_dong, parse_parcel_address


class ExtractDongTests(unittest.TestCase):
    def test_extracts_dong_from_unregistered_district(self):
        # 법정동코드 미등록 지역(송파구 삼전동)이라도 동 이름은 뽑힌다 (심평원 조회용)
        self.assertEqual(extract_dong("서울특별시 송파구 삼전동 100-1"), "삼전동")

    def test_extracts_dong_without_bun(self):
        self.assertEqual(extract_dong("서울 관악구 신림동"), "신림동")

    def test_extracts_ga_suffix(self):
        self.assertEqual(extract_dong("서울 중구 을지로3가 100"), "을지로3가")

    def test_returns_none_when_no_dong(self):
        self.assertIsNone(extract_dong("주소 없음"))


class AddressTests(unittest.TestCase):
    def test_parses_standard_parcel_address(self):
        parcel = parse_parcel_address("서울 양천구 목동 917-9")
        self.assertEqual(parcel.sigungu_code, "11470")
        self.assertEqual(parcel.bjdong_code, "10100")
        self.assertEqual(parcel.bun, 917)
        self.assertEqual(parcel.ji, 9)
        self.assertEqual(parcel.bun_padded, "0917")
        self.assertEqual(parcel.ji_padded, "0009")
        self.assertEqual(parcel.plat_gb_cd, "0")
        self.assertEqual(parcel.pnu, "1147010100109170009")

    def test_parses_address_without_ji_and_full_sido(self):
        parcel = parse_parcel_address("서울특별시 양천구 신정동 321")
        self.assertEqual(parcel.bjdong_code, "10200")
        self.assertEqual(parcel.ji, 0)
        self.assertEqual(parcel.pnu, "1147010200103210000")

    def test_parses_mountain_parcel(self):
        parcel = parse_parcel_address("서울 양천구 신월동 산 12-3")
        self.assertTrue(parcel.mountain)
        self.assertEqual(parcel.plat_gb_cd, "1")
        self.assertEqual(parcel.pnu[10], "2")

    def test_rejects_unknown_dong(self):
        with self.assertRaises(ValueError):
            parse_parcel_address("서울 강남구 역삼동 123-4")

    def test_rejects_unparseable_address(self):
        with self.assertRaises(ValueError):
            parse_parcel_address("양천구 어딘가")
