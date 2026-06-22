# A3 Report — 상세 페이지 지도 보정 + 병원 분석 섹션

## 1. 재사용한 엔드포인트

**`POST /api/verify`** (`realestate_alert/web_server.py` line ~401)

### 요청 형태
```json
{
  "address": "<지번주소 문자열>",
  "months": 6
}
```

### 응답 구조
```json
{
  "address": "string",
  "parcel": { "sigungu": "...", "dong": "...", "bun": "...", "ji": "...", "pnu": "...", ... },
  "building": { "main_purpose": "...", "floors": 5, "parking_count": 10, "elevator": true, "total_floor_area": 1200.0, "approval_date": "20050301", ... },
  "land": { "zoning": "...", "road_side": "...", "terrain": "...", "official_land_price": 1500000, ... },
  "market": { "avg_sale_price": 500000000, "avg_rent_price": 200000000, "trade_count": 12, "period": "...", ... },
  "medical": {
    "ortho_clinic_count": 2,
    "ortho_clinic_names": ["정형외과의원A", "정형외과의원B"],
    "ortho_treating_count": 5,
    "pharmacy_count": 8
  },
  "errors": {
    "medical": "optional error string if HIRA API failed",
    "building": "optional",
    "land": "optional",
    "market": "optional"
  }
}
```

`medical` 필드는 `web_server.py`의 `_attach_medical_data()` 함수가 `verify_address()` 응답에 추가로 붙임.
심평원(HIRA) 데이터는 `realestate_alert/medical_nearby.py`의 `fetch_medical_nearby(dong)` 로 조회.

---

## 2. 병원 분석 섹션 내용

`web/detail.js`에 추가된 `sec-hospital` 섹션 (`web/detail.html`)은:

- **"분석 실행" 버튼** — on-demand 호출 (페이지 로드 시 자동 실행 아님, 느린 API 고려)
- **주변 병원·약국 (심평원)** 카드:
  - 같은 동 정형외과 의원 수 (`ortho_clinic_count`)
  - 정형외과 진료 기관 수 (`ortho_treating_count`)
  - 약국 수 (`pharmacy_count`)
  - 경쟁 의원 이름 목록 (`ortho_clinic_names`)
- **공공데이터 검증 요약** key-value:
  - 용도지역, 도로접면, 지형, 공시지가, 건물 주용도, 연면적, 층수, 주차, 승강기, 사용승인일
- **실거래 시세**: 평균 매매가·전세가·거래건수·조회기간
- **전체 체크리스트 링크**: `/?address=<addr>` 로 메인 대시보드 열기
- 엔드포인트 오류 시 `dp-hosp-error` 메시지로 graceful 표시

---

## 3. 지도 보정 로직

`isValidKoreaCoord(lat, lng)` 함수:
- `lat`이 숫자이고 `33 ≤ lat ≤ 39`
- `lng`이 숫자이고 `124 ≤ lng ≤ 132`
- 위 조건 모두 만족 시만 유효한 WGS84 한국 좌표로 처리

**유효 좌표**: OSM embed iframe
```
bbox = lng±0.004, lat±0.003
https://www.openstreetmap.org/export/embed.html?bbox=...&layer=mapnik&marker=lat,lng
```

**무효 좌표 (TM좌표 등)**: 외부 지도 링크 버튼 2개
- 카카오맵: `https://map.kakao.com/?q=<주소>`
- 네이버지도: `https://map.naver.com/v5/search/<주소>`
- 주소 = `addr_jibun` 우선, fallback `addr_road`
- 주소도 없으면 "위치 정보 없음" 텍스트

---

## 4. 커밋 해시

| 커밋 | 설명 |
|------|------|
| `fe0a39e` | fix+feat: 지도 좌표 보정 + 병원 분석 섹션 (단일 커밋, 파일 분리 불가) |

> 두 가지 변경이 동일한 파일(`web/detail.js`, `web/detail.css`, `web/detail.html`)을 수정하여
> 단일 커밋으로 처리했습니다.

---

## 5. 우려 사항 / 주의

1. **`/api/verify` 응답 필드 정합성**: `verify.py`의 실제 반환 키가 `building`, `land`, `market` 필드 안에서 어떤 정확한 키를 쓰는지 서버 코드로 확인 필요. 렌더 함수는 방어적으로 `|| "—"` 처리하므로 표시는 안전하지만 필드명이 다르면 "—"로 표시될 수 있음.
2. **심평원 API 키**: `DATA_GO_KR_API_KEY` 환경변수 미설정 시 `errors.medical`에 오류 메시지. 이 경우 UI에 오류 문구가 표시됨.
3. **지도 좌표**: 원본 `latitude`/`longitude`가 TM(Transverse Mercator) 좌표계인 경우 수십만 단위 숫자라 bbox 검사로 걸러짐. OSM 서비스 자체 제한으로 너무 큰/작은 bbox는 오류 발생 가능하므로 bbox 크기 0.004/0.003 고정이 적절.
4. **`node --check` 결과**: exit 0 (오류 없음).
