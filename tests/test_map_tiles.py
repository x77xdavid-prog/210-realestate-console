import unittest
from unittest import mock

from realestate_alert.map_tiles import (
    MapTileError,
    build_vworld_tile_url,
    clear_tile_cache,
    get_map_tile,
    has_vworld_key,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-tile-body"


class BuildUrlTests(unittest.TestCase):
    def test_swaps_row_col_for_wmts(self):
        # Leaflet은 {z}/{x}/{y}, VWorld WMTS는 {z}/{row=y}/{col=x} 순서.
        url = build_vworld_tile_url(13, 6985, 3172, "KEY123")
        self.assertEqual(
            url,
            "https://api.vworld.kr/req/wmts/1.0.0/KEY123/Base/13/3172/6985.png",
        )

    def test_layer_is_configurable(self):
        url = build_vworld_tile_url(10, 1, 2, "K", layer="Satellite")
        self.assertIn("/K/Satellite/10/2/1", url)


class GetMapTileTests(unittest.TestCase):
    def setUp(self):
        clear_tile_cache()

    def test_returns_png_bytes_and_calls_fetcher_with_built_url(self):
        captured = {}

        def fake(url, referer):
            captured["url"] = url
            captured["referer"] = referer
            return PNG

        data = get_map_tile(13, 6985, 3172, key="K", fetcher=fake, referer="http://x")
        self.assertEqual(data, PNG)
        self.assertEqual(captured["url"], build_vworld_tile_url(13, 6985, 3172, "K"))
        self.assertEqual(captured["referer"], "http://x")

    def test_missing_key_raises(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(MapTileError):
                get_map_tile(13, 6985, 3172, fetcher=lambda u, r: PNG)

    def test_non_png_response_raises(self):
        with self.assertRaises(MapTileError):
            get_map_tile(13, 6985, 3172, key="K", fetcher=lambda u, r: b'{"error":"denied"}')

    def test_out_of_range_zoom_raises(self):
        with self.assertRaises(MapTileError):
            get_map_tile(99, 0, 0, key="K", fetcher=lambda u, r: PNG)

    def test_out_of_range_coord_raises(self):
        # z=10 → 유효 좌표는 0..1023. 2000은 범위 밖.
        with self.assertRaises(MapTileError):
            get_map_tile(10, 2000, 1, key="K", fetcher=lambda u, r: PNG)

    def test_cache_hit_skips_second_fetch(self):
        calls = {"n": 0}

        def fake(url, referer):
            calls["n"] += 1
            return PNG

        get_map_tile(13, 6985, 3172, key="K", fetcher=fake)
        get_map_tile(13, 6985, 3172, key="K", fetcher=fake)
        self.assertEqual(calls["n"], 1)


class HasKeyTests(unittest.TestCase):
    def test_reflects_env(self):
        with mock.patch.dict("os.environ", {"VWORLD_API_KEY": "abc"}):
            self.assertTrue(has_vworld_key())
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(has_vworld_key())


if __name__ == "__main__":
    unittest.main()
