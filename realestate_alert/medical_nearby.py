"""심평원(HIRA) 병원·약국 정보 조회 — 같은 법정동의 정형외과 의원 수와 약국 수.

data.go.kr 공통 키를 사용하지만, '병원정보서비스'와 '약국정보서비스'는
각각 별도 활용신청이 필요하다 (미신청 시 403/오류 응답).
"""

from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree

from realestate_alert.public_data import (
    Fetcher,
    PublicDataError,
    build_url,
    data_go_kr_key,
    parse_xml_items,
    xml_fetcher,
)

HOSPITAL_LIST_URL = "https://apis.data.go.kr/B551182/hospInfoServicev2/getHospBasisList"
PHARMACY_LIST_URL = "https://apis.data.go.kr/B551182/pharmacyInfoService/getParmacyBasisList"

ORTHOPEDICS_SUBJECT_CODE = "05"  # 심평원 진료과목 코드: 정형외과
CLINIC_CLASS_CODE = "31"  # 종별 코드: 의원
MAX_ROWS = "100"
ORTHO_NAME_HINT = "정형외과"


@dataclass(frozen=True)
class MedicalNearby:
    # 같은 법정동 기준. ortho_clinic_count는 이름에 '정형외과'가 든 전문의원 수(직접 경쟁),
    # ortho_treating_count는 정형외과 진료과목(dgsbjtCd=05)을 두는 의원 수(넓은 경쟁).
    ortho_clinic_count: int | None
    ortho_clinic_names: tuple[str, ...]
    pharmacy_count: int | None
    ortho_treating_count: int | None = None


def fetch_medical_nearby(
    emdong: str,
    service_key: str | None = None,
    fetcher: Fetcher | None = None,
) -> MedicalNearby:
    """법정동 이름으로 같은 동의 정형외과 의원·약국 현황을 조회한다.

    두 서비스는 별도 활용신청 대상이라 한쪽만 승인된 경우가 있다 —
    한쪽 실패는 None으로 두고 나머지는 살리며, 둘 다 실패하면 예외를 올린다.
    """
    key = service_key or data_go_kr_key()
    get = fetcher or xml_fetcher

    ortho_specialty_count: int | None = None
    ortho_treating_count: int | None = None
    ortho_names: tuple[str, ...] = ()
    pharmacy_count: int | None = None
    errors: list[str] = []

    hospital_url = build_url(
        HOSPITAL_LIST_URL,
        {
            "serviceKey": key,
            "emdongNm": emdong,
            "dgsbjtCd": ORTHOPEDICS_SUBJECT_CODE,
            "clCd": CLINIC_CLASS_CODE,
            "numOfRows": MAX_ROWS,
            "pageNo": "1",
        },
    )
    try:
        # dgsbjtCd=05는 '정형외과 진료를 보는 의원'을 모두 돌려준다(예: 신림동 50곳).
        # 그중 직접 경쟁인 정형외과 전문의원은 이름으로 추려 별도로 센다(예: 17곳).
        ortho_treating_count, all_names = _count_and_names(get(hospital_url))
        specialty = tuple(name for name in all_names if ORTHO_NAME_HINT in name)
        ortho_specialty_count = len(specialty)
        ortho_names = specialty
    except PublicDataError as error:
        errors.append(f"병원정보: {error}")

    pharmacy_url = build_url(
        PHARMACY_LIST_URL,
        {
            "serviceKey": key,
            "emdongNm": emdong,
            "numOfRows": MAX_ROWS,
            "pageNo": "1",
        },
    )
    try:
        pharmacy_count, _ = _count_and_names(get(pharmacy_url))
    except PublicDataError as error:
        errors.append(f"약국정보: {error}")

    if ortho_specialty_count is None and pharmacy_count is None:
        raise PublicDataError(" / ".join(errors) or "심평원 의료기관 조회 실패")

    return MedicalNearby(
        ortho_clinic_count=ortho_specialty_count,
        ortho_clinic_names=ortho_names,
        pharmacy_count=pharmacy_count,
        ortho_treating_count=ortho_treating_count,
    )


def medical_to_dict(summary: MedicalNearby) -> dict:
    return {
        "ortho_clinic_count": summary.ortho_clinic_count,
        "ortho_clinic_names": list(summary.ortho_clinic_names),
        "pharmacy_count": summary.pharmacy_count,
        "ortho_treating_count": summary.ortho_treating_count,
    }


def _count_and_names(body: str) -> tuple[int, tuple[str, ...]]:
    items = parse_xml_items(body)  # 오류 헤더면 여기서 PublicDataError
    total_text = ElementTree.fromstring(body).findtext(".//totalCount") or ""
    total = int(total_text) if total_text.strip().isdigit() else len(items)
    names = tuple(item["yadmNm"] for item in items if item.get("yadmNm"))
    return total, names
