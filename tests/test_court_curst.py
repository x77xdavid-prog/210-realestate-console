import json
import unittest

from realestate_alert.court_curst import build_curst_body, fetch_tenants, parse_curst

# 합성 픽스처 (실명 대신 가명) — 실제 selectCurstExmndc.on 응답 구조를 모사
CURST_PAYLOAD = {
    "status": 200,
    "data": {
        "dma_curstExmnMngInf": {
            "exmndcSndngYmd": "20260401",
            "exmndcRcptnYmd": "20260402",
            "exmnDtDts": "2026년03월19일14시40분 ",
        },
        "dlt_ordTsLserLtn": [
            {
                "intrpsNm": "홍길동",
                "objctDtlAddr": ", 102호(샘플동)",
                "lesUsgDts": "주거",
                "lesDposDts": "100,000,000",
                "mmrntAmtDts": "500,000",
                "mvinDtlCtt": "2016.10.20.",
                "rgstryCrtcpCfmtnCtt": "2016.10.21.",
                "lesPartCtt": "전부",
                "gdsPossCtt": "임차인 점유",
                "lesDtsRmk": "-",
            },
            # 빈 행 (이름/임차정보 없음) → 제외돼야 함
            {"intrpsNm": "", "lesDposDts": "", "mvinDtlCtt": "", "gdsPossCtt": "-"},
        ],
        "dlt_ordTsRlet": [
            {
                "rprsLtnoAddr": "508-123",
                "objctArDts": "84㎡",
                "lesCnt": 1,
                "gdsPossCtt": "임차인 점유",
                "rletLstRmk": "",
            }
        ],
    },
}


class ParseCurstTests(unittest.TestCase):
    def test_extracts_tenant_fields(self):
        result = parse_curst(CURST_PAYLOAD)
        self.assertEqual(len(result["tenants"]), 1)  # 빈 행 제외
        t = result["tenants"][0]
        self.assertEqual(t["name"], "홍길동")
        self.assertEqual(t["deposit"], "100,000,000")
        self.assertEqual(t["rent"], "500,000")
        self.assertEqual(t["move_in"], "2016.10.20.")
        self.assertEqual(t["confirm"], "2016.10.21.")
        self.assertEqual(t["part"], "전부")
        self.assertEqual(t["note"], "")  # "-" 는 빈 값으로 정리

    def test_occupancy_and_survey(self):
        result = parse_curst(CURST_PAYLOAD)
        self.assertEqual(len(result["occupancy"]), 1)
        self.assertEqual(result["occupancy"][0]["tenant_count"], 1)
        self.assertEqual(result["occupancy"][0]["area"], "84㎡")
        self.assertEqual(result["survey"]["sent_date"], "20260401")
        self.assertEqual(result["survey"]["exam_dates"], "2026년03월19일14시40분")

    def test_empty_payload(self):
        result = parse_curst({"data": {}})
        self.assertEqual(result["tenants"], [])
        self.assertEqual(result["occupancy"], [])
        self.assertIsNone(result["survey"]["sent_date"])


class BuildBodyTests(unittest.TestCase):
    def test_body_shape(self):
        body = build_curst_body("20080130025092", "B000210")["dma_srchCurstExmn"]
        self.assertEqual(body["csNo"], "20080130025092")
        self.assertEqual(body["cortOfcCd"], "B000210")
        self.assertEqual(body["auctnInfOriginDvsCd"], "2")


class FetchTenantsTests(unittest.TestCase):
    def test_injected_fetcher_parses(self):
        captured = {}

        def fake(body):
            captured["body"] = body
            return json.dumps(CURST_PAYLOAD)

        result = fetch_tenants("20080130025092", "B000210", fetcher=fake)
        self.assertEqual(len(result["tenants"]), 1)
        self.assertEqual(captured["body"]["dma_srchCurstExmn"]["csNo"], "20080130025092")

    def test_fetcher_error_absorbed(self):
        def boom(body):
            raise RuntimeError("network down")

        result = fetch_tenants("c", "o", fetcher=boom)
        self.assertEqual(result["tenants"], [])
        self.assertEqual(result["occupancy"], [])

    def test_bad_json_absorbed(self):
        result = fetch_tenants("c", "o", fetcher=lambda body: "<html>error</html>")
        self.assertEqual(result["tenants"], [])


if __name__ == "__main__":
    unittest.main()
