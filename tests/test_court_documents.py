import base64
import json
import unittest

from realestate_alert.court_documents import (
    build_sale_spec_log_body,
    build_viewer_url,
    extract_doc_params,
    sale_spec_viewer_url,
)

VIEWER_BASE = "https://ecfs.scourt.go.kr/sgvo/websquare/websquare.html?w2xPath=/sgvo/ui/sgvo200/SGVO201M01.xml"


def _detail(orv="ORV123", ecdoc="ECDOC456"):
    return {"data": {"dma_result": {"dspslGdsDxdyInfo": {
        "orvParam": orv, "dspslGdsSpcfcEcdocId": ecdoc,
    }}}}


class _FakeSession:
    """주입용 가짜 세션 — 정해진 상세/로그 응답을 돌려준다."""

    def __init__(self, detail, log):
        self._detail = detail
        self._log = log
        self.detail_calls = []
        self.log_calls = []

    def post_detail(self, body):
        self.detail_calls.append(body)
        return self._detail

    def post_sale_spec_log(self, body):
        self.log_calls.append(body)
        return self._log


class ExtractDocParamsTests(unittest.TestCase):
    def test_extracts_orv_and_ecdoc(self):
        orv, ecdoc = extract_doc_params(_detail("A", "B"))
        self.assertEqual((orv, ecdoc), ("A", "B"))

    def test_missing_fields_return_empty(self):
        orv, ecdoc = extract_doc_params({"data": {"dma_result": {}}})
        self.assertEqual((orv, ecdoc), ("", ""))


class BuildLogBodyTests(unittest.TestCase):
    def test_body_shape(self):
        body = build_sale_spec_log_body("20080130025092", "B000210", "1", "ORV", "EC")
        log = body["dma_dspslGdsSpecLog"]
        self.assertEqual(log["csNo"], "20080130025092")
        self.assertEqual(log["cortOfcCd"], "B000210")
        self.assertEqual(log["dspslGdsSeq"], 1)  # 정수로 변환
        self.assertEqual(log["orvParam"], "ORV")
        self.assertEqual(log["dspslGdsSpcfcEcdocId"], "EC")
        self.assertEqual(log["cortAuctnMbrsId"], "NONUSER")
        self.assertEqual(log["docFlag"], "1")


class BuildViewerUrlTests(unittest.TestCase):
    def test_paramdata_roundtrips(self):
        url = build_viewer_url(VIEWER_BASE, "ENC%2Bparam")
        self.assertTrue(url.startswith(VIEWER_BASE + "?paramData="))
        encoded = url.split("paramData=", 1)[1]
        decoded = json.loads(base64.b64decode(encoded).decode("utf-8"))
        self.assertEqual(decoded["encParam"], "ENC%2Bparam")
        self.assertEqual(decoded["pspTkn"], "NA")
        self.assertEqual(decoded["pspSid"], "NA")


class SaleSpecViewerUrlTests(unittest.TestCase):
    def test_returns_deeplink_with_injected_session(self):
        log = {"data": {"dma_dspslSpcfcInfo": {"url": VIEWER_BASE, "encParam": "ENCabc"}}}
        sess = _FakeSession(_detail("ORVx", "ECx"), log)
        url = sale_spec_viewer_url("20080130025092", "B000210", "1", session=sess)
        self.assertIsNotNone(url)
        self.assertTrue(url.startswith(VIEWER_BASE + "?paramData="))
        # 로그 호출 바디에 상세에서 뽑은 orvParam/ecdoc가 실렸는지
        log_body = sess.log_calls[0]["dma_dspslGdsSpecLog"]
        self.assertEqual(log_body["orvParam"], "ORVx")
        self.assertEqual(log_body["dspslGdsSpcfcEcdocId"], "ECx")

    def test_missing_orv_returns_none(self):
        sess = _FakeSession(_detail("", ""), {})
        self.assertIsNone(sale_spec_viewer_url("c", "o", "1", session=sess))

    def test_missing_encparam_returns_none(self):
        log = {"data": {"dma_dspslSpcfcInfo": {"url": VIEWER_BASE}}}  # encParam 없음
        sess = _FakeSession(_detail("ORV", "EC"), log)
        self.assertIsNone(sale_spec_viewer_url("c", "o", "1", session=sess))

    def test_session_error_absorbed_to_none(self):
        class Boom:
            def post_detail(self, body):
                raise RuntimeError("network down")

            def post_sale_spec_log(self, body):
                raise RuntimeError("network down")

        self.assertIsNone(sale_spec_viewer_url("c", "o", "1", session=Boom()))


if __name__ == "__main__":
    unittest.main()
