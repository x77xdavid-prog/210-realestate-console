import base64, io, unittest
from pathlib import Path
import tempfile
from realestate_alert.photos import save_photos, PIC_ORDER

def _tiny_jpeg_b64():
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (4, 4), (200, 30, 30)).save(buf, "JPEG")
    return base64.b64encode(buf.getvalue()).decode()

class PhotoTests(unittest.TestCase):
    def test_saves_and_orders(self):
        b64 = _tiny_jpeg_b64()
        pics = [
            {"cortAuctnPicSeq": "1", "cortAuctnPicDvsCd": "000244", "picFile": b64},  # 지적도 → 뒤
            {"cortAuctnPicSeq": "2", "cortAuctnPicDvsCd": "000241", "picFile": b64},  # 외관 → 앞
        ]
        with tempfile.TemporaryDirectory() as tmp:
            paths = save_photos(pics, "court:2024타경58264-1", Path(tmp))
            self.assertEqual(len(paths), 2)
            first = paths[min(paths)]
            self.assertTrue(first.endswith("/01.jpg"))
            self.assertTrue((Path(tmp) / first).exists())

    def test_bad_base64_skipped(self):
        pics = [{"cortAuctnPicSeq": "1", "cortAuctnPicDvsCd": "000241", "picFile": "!!notb64!!"}]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(save_photos(pics, "x", Path(tmp)), {})
