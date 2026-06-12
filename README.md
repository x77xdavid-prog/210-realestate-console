# 부동산 매물 자동검색 알림 서비스

병원 건물 매입을 위한 매물 검토 콘솔입니다. 로컬 JSON/API 매물 소스를 읽어 조건에 맞는 신규 매물만 알림으로 보내고, 웹 대시보드에서 관심매물·매물장·네이버 부동산 연동을 한 화면에서 관리합니다.

## 실행

```powershell
python -m realestate_alert init-db --config config.example.json
python -m realestate_alert run-once --config config.example.json
python -m realestate_alert serve-web --config config.example.json --port 8765
python -m realestate_alert export-registry-targets --config config.example.json --output data/registry-targets.csv
```

`serve-web` 실행 후 http://127.0.0.1:8765/ 를 열면 대시보드가 표시됩니다. `watch` 명령을 사용하면 `interval_seconds` 간격으로 자동 스캔합니다.

## 대시보드

화이트 톤의 3D 인터랙티브 콘솔(210정형외과 브랜딩)로 구성됩니다.

- **현황**: 수집/조건 일치/신규/관심 매물 수를 카운트업 애니메이션으로 표시
- **신규 매물 배너**: 최근 72시간 내 등록된 매물을 소스별(네이버·온비드) 카운트와 함께 상단에 강조. 카드에는 "N시간 전 등록" 경과 시간과 24시간 이내 펄스 NEW 배지 표시, 보드에서 신규 매물 우선 정렬
- **매물 보드**: 전체 · ★신규 · ♥관심 · ⛳필수조건 필터 칩과 3D 틸트 카드. 카드마다 네이버 부동산/지도 버튼, 관심 하트, 매물장 추가 버튼 제공
- **필수조건 검색**: 대지·연면적(평 환산)·주차·승강기·용도지역 조건으로 수집 매물을 ✅충족/❓확인 필요(데이터 부족)/미달 3그룹으로 분류. "기존 건물(대지 150평·연면적 600평)" / "신축용 토지" 프리셋 제공, 조건은 localStorage에 유지
- **매물장**: 추가한 매물의 상태(검토중/연락 완료/방문 예정/협상중/보류/계약 검토)와 메모(자동 저장)를 관리하고 CSV로 내보내기
- **체크리스트 검토**: 매물장 매물을 [병원건물 매입·신축 체크리스트](docs/병원건물_매입_신축_체크리스트.md) 기준으로 검토. 프로필 3종(기존 건물 사용/철거 후 신축/나대지 신축)별 항목이 다르며, 공공데이터로 자동 판정(용도지역·도로접면·주차·승강기·시세·노후도)하고 나머지는 수동 체크. 치명 항목 부적합 시 즉시 "부적합", 그 외 가중 점수로 A~D 등급(3D 플립 배지) 산출
- **지도**: 매물 필지에 핀이 표시되는 임베드 지도와 네이버 부동산(좌표 중심)·네이버 지도 새 탭 버튼, 공공데이터 검증, 매입 계산 반영 버튼 제공
- **매입 계산**: 취득세·중개보수 포함 필요 현금 추정

`serve-web`으로 실행하면 관심매물과 매물장이 SQLite에 저장됩니다. `web/index.html`을 파일로 직접 열면 정적 모드로 동작하며 브라우저 localStorage에 저장됩니다.

## Gmail 신규 매물 알림

신규 매물이 발견되면 Gmail로 알림 메일(네이버 부동산/지도 링크 포함)을 발송합니다.

1. Google 계정 → 보안 → 2단계 인증 활성화 → **앱 비밀번호** 발급
2. 환경 변수에 앱 비밀번호 설정 (소스 코드/설정 파일에 저장하지 않습니다)

   ```powershell
   # 현재 세션만
   $env:GMAIL_APP_PASSWORD = "발급받은 16자리 앱 비밀번호"
   # 영구 등록
   setx GMAIL_APP_PASSWORD "발급받은 16자리 앱 비밀번호"
   ```

3. config의 `notifiers`에 gmail 항목 설정

   ```json
   {
     "type": "gmail",
     "sender": "보내는 Gmail 주소",
     "recipients": ["받는 주소1", "받는 주소2"],
     "password_env": "GMAIL_APP_PASSWORD"
   }
   ```

환경 변수가 없으면 메일 발송을 건너뛰고 콘솔에 안내만 출력하므로, 설정 전에도 다른 기능은 정상 동작합니다.

## 공공 API 매물 검증

매물 주소(지번) 하나로 건축물대장·토지정보·실거래 시세를 한 번에 조회합니다.

```powershell
python -m realestate_alert verify-address --address "서울 양천구 목동 917-9" --months 6
```

대시보드에서는 지도 패널의 **공공데이터 검증** 버튼으로 같은 리포트를 확인하고, 조회된 값(층수, 주차, 승강기, 승인연도, 건폐율/용적률, 용도지역, 도로접면)이 매물의 빈 필드에 자동 반영됩니다.

### API 키 발급 (모두 무료)

| 키 | 환경 변수 | 발급처 | 사용 데이터 |
|---|---|---|---|
| 공공데이터포털 | `DATA_GO_KR_API_KEY` | [data.go.kr](https://www.data.go.kr) 회원가입 → 아래 두 서비스에 각각 활용신청(자동승인) → 마이페이지 일반 인증키(Decoding) | [건축물대장(건축HUB)](https://www.data.go.kr/data/15134735/openapi.do), [상업업무용 실거래가](https://www.data.go.kr/data/15126463/openapi.do) |
| 브이월드 | `VWORLD_API_KEY` | [vworld.kr](https://www.vworld.kr) 회원가입 → 오픈API → 인증키 발급 | 토지이용계획(용도지역), 토지특성(도로접면), 개별공시지가 |

```powershell
setx DATA_GO_KR_API_KEY "발급받은 인증키"
setx VWORLD_API_KEY "발급받은 인증키"
```

키가 없으면 해당 소스만 건너뛰고 리포트에 발급 안내가 표시됩니다. 현재 지번 파싱은 양천구(목동·신정동·신월동) 기준이며, 다른 지역은 `realestate_alert/address.py`의 `BJDONG_CODES`에 법정동코드를 추가하면 됩니다.

### 온비드 공매 매물 소스

캠코 온비드의 현재 입찰 중/예정 공매 부동산을 매물 소스로 자동 수집합니다. config의 `sources`에 추가하면 스캔할 때마다 지역 내 공매 물건이 매물 보드와 알림에 포함됩니다.

```json
{ "type": "onbid", "sido": "서울특별시", "sigungu": "양천구" }
```

`DATA_GO_KR_API_KEY` 발급 후 [차세대 온비드 부동산 물건목록 조회서비스](https://www.data.go.kr/data/15157207/openapi.do)에 활용신청이 필요합니다. 키가 없으면 해당 소스만 건너뜁니다. 공매 물건은 보증금/월세 대신 감정가·최저입찰가·입찰 기간이 메모에 표시되며, 온비드(onbid.co.kr)에서 물건관리번호로 검색해 상세를 확인합니다.

## 건물·토지 매입 검토

- `건물·토지 매입 조건표`에서 대지, 건평/연면적, 층수, 주차, 엘리베이터, 승인연도 조건을 확인합니다.
- `건물·토지 조건 설정` 모달에서 건물 매입 조건과 토지 신축 가능성 조건을 수정할 수 있습니다.
- 토지 조건은 용도지역, 접도 폭, 건폐율, 용적률, 건축 가능 여부, 주차장 설치, 병원 용도 가능 여부를 확인하도록 구성했습니다.
- 매물 지도 팝업에는 선택 매물의 조건 판정, 대지, 건평, 층수, 주차, 용도지역, 접도, 건폐율/용적률, 신축/매입 메모, 네이버 부동산 링크가 표시됩니다.

등기 파일 위험 신호 분석:

```powershell
python -m realestate_alert analyze-registry --file path\to\registry.txt
```

매입 비용 추정:

```powershell
python -m realestate_alert estimate-purchase --purchase-price 1000000000 --loan-amount 600000000 --cash-available 450000000 --acquisition-tax-rate 0.046 --brokerage-rate 0.009 --legal-fee 2000000 --other-costs 3000000
```

## 주의

인터넷등기소 로그인, 결제, 보안문자는 사용자가 직접 처리해야 합니다. 이 서비스는 등기 열람 대상 목록 생성, 사용자가 내려받은 파일 분석, 위험 키워드 표시를 담당합니다.

세금과 중개보수는 설정값 기반 추정치입니다. 물건 종류, 지역, 금액 구간, 법령 변경에 따라 달라질 수 있으므로 실제 매입 전 최신 기준과 전문가 검토가 필요합니다.
