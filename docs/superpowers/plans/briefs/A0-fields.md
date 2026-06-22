# A0 — 경매 상세 서브리스트 필드 매핑

캡처 사건: **2025타경596** (단독주택) — 서울남부지방법원, 양천구  
샘플 파일: `samples/court-detail-populated.sample.json`  
비교 참조: `samples/court-detail-2024ta58264.sample.json` (다세대주택, rgltLand 참조용)

---

## 1. `gdsNotSugtBldLsstAll` — 제시외건물 목록

> 경매 목적물에 포함되지 않은 지상 건물 (법원이 "제시외"로 표시). 단독주택·다가구 사건에서 주로 나타남.

| 필드명 | 한글 의미 | 예시값 |
|--------|-----------|--------|
| `cortOfcCd` | 법원 코드 | `"B000212"` |
| `csNo` | 사건번호 (내부 코드) | `"20250130000596"` |
| `dspslObjctSeq` | 처분 물건 순번 | `2` |
| `sugtBsdsBldSeq` | 제시외건물 순번 | `1` |
| `etcUsgCtt` | 기타 용도 내용 (건물 용도명) | `"창고"` (garbled) |
| `bldStrcDts` | 건물 구조 상세 | `"목조 기와지붕"` (garbled) |
| `bldArDts` | 건물 면적 상세 (㎡ 포함 문자열) | `"56㎡"` (garbled) |
| `evlAmt` | 감정 평가액 (원) | `4800000` |
| `sugtBsdsBldRmk` | 제시외건물 비고 | `"미등기"` (garbled) |

---

## 2. `rgltLandLstAll` — 토지 지역지구 규제 목록

> 경매 물건 토지에 적용되는 용도지역·지구 규제 항목. 대지·단독주택 등 토지가 있는 사건에서 나타남.  
> (2025타경596은 단독주택이나 이 항목 0건. 필드명은 2024타경58264 다세대 샘플 참조.)

| 필드명 | 한글 의미 | 예시값 |
|--------|-----------|--------|
| `cortOfcCd` | 법원 코드 | `"B000215"` |
| `csNo` | 사건번호 (내부 코드) | `"20240130058264"` |
| `dspslObjctSeq` | 처분 물건 순번 | `1` |
| `rgltLandSeq` | 규제 토지 순번 | `1` |
| `rletCarUnqNo` | 부동산 고유번호 | `"27012019014537"` |
| `rletDvsDts` | 부동산 구분 상세 (지목명) | `"대"` (garbled) |
| `landArDts` | 토지 면적 상세 | `"69㎡"` (garbled) |
| `landLdcgDts` | 토지 지목 상세 | `"대"` (garbled) |
| `auctnRgltKndCd` | 경매 규제 종류 코드 | `"12401"` |
| `rgltRateDnmnVal` | 규제 비율 분모값 | `"521"` |
| `rgltRateNmrtVal` | 규제 비율 분자값 | `"44"` |
| `rletIndctDts` | 부동산 표시 상세 (주소 포함) | `"서울특별시…5-38"` (garbled) |
| `rgltLandSdNm` | 규제 토지 시/도명 | `"서울특별시"` (garbled) |
| `rgltLandSggNm` | 규제 토지 시군구명 | `"마포구"` (garbled) |
| `rgltLandEmdNm` | 규제 토지 읍면동명 | `"아현동"` (garbled) |
| `rgltLandRiNm` | 규제 토지 리명 | `null` |
| `rgltLandLtnoAddr` | 규제 토지 지번 주소 | `"5-38"` |
| `rgltLandNo` | 규제 토지 번호 | `1` |

---

## 3. `bldSdtrDtlLstAll` — 건물 상세 목록

> 경매 목적물의 건물 구조·면적 상세. 단독주택·다세대 등 건물이 있는 사건에서 나타남.

| 필드명 | 한글 의미 | 예시값 |
|--------|-----------|--------|
| `cortOfcCd` | 법원 코드 | `"B000212"` |
| `csNo` | 사건번호 (내부 코드) | `"20250130000596"` |
| `dspslObjctSeq` | 처분 물건 순번 | `2` |
| `bldSdtrSeq` | 건물 상세 순번 | `1` |
| `rletCarUnqNo` | 부동산 고유번호 | `"11611996632849"` |
| `rletDvsDts` | 부동산 구분 상세 (건물 종류) | `"일반건물"` (garbled) |
| `bldSdtrDtlDts` | 건물 상세 내용 (구조·면적 자유텍스트) | `"목조 스레이트지붕\n43.97㎡"` (garbled) |

---

## 4. `gdsRletStLtnoLstAll` — 물건 부동산 상태 지번 목록

> 경매 목적물의 지번 주소 및 도로명 주소 목록. 지번이 여러 개일 때 여러 항목.

| 필드명 | 한글 의미 | 예시값 |
|--------|-----------|--------|
| `cortOfcCd` | 법원 코드 | `"B000212"` |
| `csNo` | 사건번호 (내부 코드) | `"20250130000596"` |
| `dspslObjctSeq` | 처분 물건 순번 | `2` |
| `rletStSeq` | 부동산 상태 순번 | `1` |
| `adongSdCd` | 행정동 시도 코드 | `"11"` |
| `adongSggCd` | 행정동 시군구 코드 | `"560"` |
| `adongEmdCd` | 행정동 읍면동 코드 | `"132"` |
| `adongRiCd` | 행정동 리 코드 | `"00"` |
| `rletStLtnoAddr` | 지번 주소 (본번-부번) | `"7-31"` |
| `adongSdNm` | 시도명 | `"서울특별시"` (garbled) |
| `adongSggNm` | 시군구명 | `"양천구"` (garbled) |
| `adongEmdNm` | 읍면동명 | `"신정동"` (garbled) |
| `adongRiNm` | 리명 | `null` |
| `auctnLstDvsCd` | 경매 목록 구분 코드 (`02`=토지·건물, `03`=집합) | `"02"` |
| `mclDspslGdsLstUsgCd` | 중분류 처분물건 목록 용도 코드 | `"20100"` |
| `rdnmSdNm` | 도로명 시도명 | `"서울특별시"` (garbled) |
| `rdnmSggNm` | 도로명 시군구명 | `"양천구"` (garbled) |
| `rdEubMyun` | 도로명 읍면 | `null` |
| `rdnm` | 도로명 | `"신정이펜하우스59로"` (garbled) |
| `rdnmBldNo` | 도로명 건물번호 | `"40-2"` |
| `rdnmRefcAddr` | 도로명 참조 주소 (괄호 주소) | `null` |
| `addrTypCd` | 주소 유형 코드 (`A`=행정동, `R`=도로명) | `"A"` |

---

## 5. `dstrtDemnInfo` — 배당종기 정보

> 배당요구 종기일 및 배당 구분 코드.

| 필드명 | 한글 의미 | 예시값 |
|--------|-----------|--------|
| `orddcsDvsCd` | 명령 결정 구분 코드 (`021`=배당요구종기결정) | `"021"` |
| `dstrtDemnLstprdYmd` | 배당요구 종기일 (YYYYMMDD) | `"20251015"` |

---

## 비고

- 한글 문자열 값은 API가 CP949 인코딩으로 응답하는 것을 UTF-8로 잘못 해석해 garbled 상태. 필드 **키** 자체는 ASCII이므로 파싱에는 문제없음.
- `gdsNotSugtBldLsstAll`은 단독주택·다가구주택에서 나타나며, 집합건물(다세대·아파트) 사건에서는 비어있음(`[[]]`).
- `rgltLandLstAll`은 규제 적용 토지가 복수일 때 항목이 여럿. 2024타경58264 샘플에서 8개 확인.
- `auctnRgltKndCd` 코드 매핑(예: `12401`)은 법원경매 내부 분류 — 추후 역방향 조회 필요.
