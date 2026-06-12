import json
import unittest

from realestate_alert.land_info import (
    fetch_land_summary,
    fetch_land_use_names,
    geocode_parcel,
    road_width_hint,
)

LAND_USE_JSON = json.dumps(
    {
        "landUses": {
            "field": [
                {"prposAreaDstrcCodeNm": "제2종일반주거지역", "cnflcAtNm": "포함", "stdrYear": "2025"},
                {"prposAreaDstrcCodeNm": "가축사육제한구역", "cnflcAtNm": "저촉", "stdrYear": "2025"},
                {"prposAreaDstrcCodeNm": "제2종일반주거지역", "cnflcAtNm": "포함", "stdrYear": "2024"},
            ]
        }
    },
    ensure_ascii=False,
)

# 래퍼 키 이름이 다른 경우도 파싱되는지 확인
LAND_CHAR_JSON = json.dumps(
    {
        "landCharacteristicss": {
            "items": [
                {
                    "stdrYear": "2024",
                    "roadSideCodeNm": "중로한면",
                    "ladUseSittnNm": "상업용",
                    "tpgrphHgCodeNm": "평지",
                    "tpgrphFrmCodeNm": "세로장방",
                },
                {
                    "stdrYear": "2025",
                    "roadSideCodeNm": "광대한면",
                    "ladUseSittnNm": "상업용",
                    "tpgrphHgCodeNm": "평지",
                    "tpgrphFrmCodeNm": "세로장방",
                },
            ]
        }
    },
    ensure_ascii=False,
)

LAND_PRICE_JSON = json.dumps(
    {
        "indvdLandPrices": {
            "field": [
                {"stdrYear": "2024", "pblntfPclnd": "5800000"},
                {"stdrYear": "2025", "pblntfPclnd": "6120000"},
            ]
        }
    },
    ensure_ascii=False,
)


def _route_fetcher(url: str) -> str:
    if "getLandUseAttr" in url:
        return LAND_USE_JSON
    if "getLandCharacteristics" in url:
        return LAND_CHAR_JSON
    if "getIndvdLandPriceAttr" in url:
        return LAND_PRICE_JSON
    raise AssertionError(f"unexpected url: {url}")


class LandInfoTests(unittest.TestCase):
    def test_land_use_excludes_conflicts_and_duplicates(self):
        names = fetch_land_use_names("1147010100109170009", key="k", fetcher=_route_fetcher)
        self.assertEqual(names, ["제2종일반주거지역"])

    def test_land_summary_uses_latest_year(self):
        summary = fetch_land_summary("1147010100109170009", key="k", fetcher=_route_fetcher)
        self.assertEqual(summary.road_side, "광대한면")
        self.assertEqual(summary.road_width_hint_m, 25.0)
        self.assertEqual(summary.official_price_per_m2, 6120000)
        self.assertEqual(summary.official_price_year, "2025")
        self.assertEqual(summary.land_use_situation, "상업용")

    def test_geocode_parcel_parses_point_and_caches(self):
        payload = json.dumps(
            {
                "response": {
                    "status": "OK",
                    "result": {"crs": "EPSG:4326", "point": {"x": "126.864064", "y": "37.544404"}},
                }
            }
        )
        calls = []

        def fake_fetch(url):
            calls.append(url)
            return payload

        first = geocode_parcel("서울특별시 양천구 목동 324-18 (테스트)", key="k", fetcher=fake_fetch)
        second = geocode_parcel("서울특별시 양천구 목동 324-18 (테스트)", key="k", fetcher=fake_fetch)

        self.assertEqual(first, (37.544404, 126.864064))
        self.assertEqual(second, first)
        self.assertEqual(len(calls), 1)  # 두 번째 호출은 캐시 사용

    def test_geocode_parcel_returns_none_when_not_found(self):
        payload = json.dumps({"response": {"status": "NOT_FOUND"}})
        result = geocode_parcel("존재하지 않는 주소 (테스트)", key="k", fetcher=lambda url: payload)
        self.assertIsNone(result)

    def test_road_width_hint_mapping(self):
        self.assertEqual(road_width_hint("소로각지"), 8.0)
        self.assertEqual(road_width_hint("세로한면(가)"), 4.0)
        self.assertEqual(road_width_hint("세로각지(불)"), 3.0)
        self.assertEqual(road_width_hint("맹지"), 0.0)
        self.assertIsNone(road_width_hint(None))
        self.assertIsNone(road_width_hint("알수없음"))
