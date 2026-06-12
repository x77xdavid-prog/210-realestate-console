import unittest

from realestate_alert.address import parse_parcel_address


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
