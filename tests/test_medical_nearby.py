import unittest

from realestate_alert.medical_nearby import (
    HOSPITAL_LIST_URL,
    PHARMACY_LIST_URL,
    MedicalNearby,
    fetch_medical_nearby,
    medical_to_dict,
)
from realestate_alert.public_data import PublicDataError

HOSPITAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item><yadmNm>목동튼튼정형외과의원</yadmNm><clCdNm>의원</clCdNm></item>
      <item><yadmNm>바른정형외과의원</yadmNm><clCdNm>의원</clCdNm></item>
    </items>
    <numOfRows>50</numOfRows><pageNo>1</pageNo><totalCount>4</totalCount>
  </body>
</response>
"""

PHARMACY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>00</resultCode><resultMsg>NORMAL SERVICE.</resultMsg></header>
  <body>
    <items>
      <item><yadmNm>건강약국</yadmNm></item>
    </items>
    <numOfRows>50</numOfRows><pageNo>1</pageNo><totalCount>7</totalCount>
  </body>
</response>
"""

ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>30</resultCode><resultMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</resultMsg></header>
</response>
"""


def _fake_fetcher(url: str) -> str:
    if url.startswith(HOSPITAL_LIST_URL):
        return HOSPITAL_XML
    if url.startswith(PHARMACY_LIST_URL):
        return PHARMACY_XML
    raise AssertionError(f"예상하지 못한 URL: {url}")


def _pharmacy_denied_fetcher(url: str) -> str:
    if url.startswith(HOSPITAL_LIST_URL):
        return HOSPITAL_XML
    raise PublicDataError("HTTP Error 403: Forbidden")


class MedicalNearbyTests(unittest.TestCase):
    def test_fetch_counts_and_names(self):
        result = fetch_medical_nearby("목동", service_key="test-key", fetcher=_fake_fetcher)
        self.assertEqual(result.ortho_clinic_count, 4)  # totalCount 우선
        self.assertEqual(result.ortho_clinic_names, ("목동튼튼정형외과의원", "바른정형외과의원"))
        self.assertEqual(result.pharmacy_count, 7)

    def test_partial_success_when_pharmacy_denied(self):
        # 병원 API만 승인된 상태 — 병원 데이터는 살리고 약국만 None
        result = fetch_medical_nearby("목동", service_key="test-key", fetcher=_pharmacy_denied_fetcher)
        self.assertEqual(result.ortho_clinic_count, 4)
        self.assertIsNone(result.pharmacy_count)

    def test_error_raises_when_all_sources_fail(self):
        with self.assertRaises(PublicDataError):
            fetch_medical_nearby("목동", service_key="bad", fetcher=lambda url: ERROR_XML)

    def test_medical_to_dict(self):
        summary = MedicalNearby(
            ortho_clinic_count=2,
            ortho_clinic_names=("a의원",),
            pharmacy_count=0,
        )
        payload = medical_to_dict(summary)
        self.assertEqual(payload["ortho_clinic_count"], 2)
        self.assertEqual(payload["ortho_clinic_names"], ["a의원"])
        self.assertEqual(payload["pharmacy_count"], 0)


if __name__ == "__main__":
    unittest.main()
