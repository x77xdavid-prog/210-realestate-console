from __future__ import annotations

import re
from dataclasses import dataclass

# 법정동코드: 행정표준코드관리시스템(code.go.kr) 기준.
# 시군구코드 5자리 + 법정동코드 5자리. 필요 지역이 늘어나면 여기에 추가한다.
BJDONG_CODES: dict[tuple[str, str], tuple[str, str]] = {
    ("양천구", "목동"): ("11470", "10100"),
    ("양천구", "신정동"): ("11470", "10200"),
    ("양천구", "신월동"): ("11470", "10300"),
}

_ADDRESS_PATTERN = re.compile(
    r"(?:서울(?:특별시)?\s+)?"
    r"(?P<sigungu>\S+구)\s+"
    r"(?P<dong>\S+(?:동|가))\s+"
    r"(?P<mountain>산\s*)?"
    r"(?P<bun>\d{1,4})(?:-(?P<ji>\d{1,4}))?"
)


@dataclass(frozen=True)
class ParcelAddress:
    sigungu: str
    dong: str
    bun: int
    ji: int
    mountain: bool
    sigungu_code: str
    bjdong_code: str

    @property
    def full_bjdong_code(self) -> str:
        return f"{self.sigungu_code}{self.bjdong_code}"

    @property
    def pnu(self) -> str:
        """필지고유번호 19자리: 법정동(10) + 필지구분(1: 일반=1, 산=2) + 본번(4) + 부번(4)."""
        parcel_type = "2" if self.mountain else "1"
        return f"{self.full_bjdong_code}{parcel_type}{self.bun:04d}{self.ji:04d}"

    @property
    def bun_padded(self) -> str:
        return f"{self.bun:04d}"

    @property
    def ji_padded(self) -> str:
        return f"{self.ji:04d}"

    @property
    def plat_gb_cd(self) -> str:
        """건축물대장 대지구분코드: 0=대지, 1=산."""
        return "1" if self.mountain else "0"


def parse_parcel_address(address: str) -> ParcelAddress:
    """'서울 양천구 목동 917-9' 형태의 지번 주소를 공공 API 파라미터로 분해한다."""
    match = _ADDRESS_PATTERN.search(address.strip())
    if not match:
        raise ValueError(f"지번 주소 형식을 해석할 수 없습니다: {address}")
    sigungu = match.group("sigungu")
    dong = match.group("dong")
    codes = BJDONG_CODES.get((sigungu, dong))
    if codes is None:
        supported = ", ".join(f"{gu} {d}" for gu, d in sorted(BJDONG_CODES))
        raise ValueError(f"법정동코드 미등록 지역입니다: {sigungu} {dong} (지원: {supported})")
    sigungu_code, bjdong_code = codes
    return ParcelAddress(
        sigungu=sigungu,
        dong=dong,
        bun=int(match.group("bun")),
        ji=int(match.group("ji") or 0),
        mountain=match.group("mountain") is not None,
        sigungu_code=sigungu_code,
        bjdong_code=bjdong_code,
    )
