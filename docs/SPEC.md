# Spec: 부동산 매물 자동검색 알림 서비스

## Objective
부동산 매물 조건을 설정해 두면, 등록된 검색 소스에서 신규 매물을 주기적으로 확인하고 조건에 맞는 매물만 알림으로 전달하는 로컬 실행형 서비스.

주 사용자는 210정형외과 관련 부동산 후보지를 반복 확인해야 하는 사용자다. 성공 상태는 같은 매물을 중복 알림하지 않고, 조건에 맞는 신규 매물을 빠르게 확인할 수 있는 것이다.
추가로 후보 매물의 등기 확인 대상 목록, 등기 PDF 위험 신호, 자기자본 비율, 취득 관련 세금 및 중개보수 추정치를 함께 관리한다.

## Assumptions
1. 첫 버전은 로컬 PC에서 실행하는 CLI 서비스로 만든다.
2. 외부 사이트의 비공개 API나 우회 수집은 하지 않는다.
3. 검색 소스는 공개 JSON/API 또는 사용자가 제공한 JSON 파일을 먼저 지원한다.
4. 알림은 콘솔 출력, 웹훅, 텔레그램 중 설정된 채널로 보낸다.
5. 사이트별 크롤러는 이후 실제 대상 사이트와 허용 방식이 확정되면 어댑터로 추가한다.
6. 인터넷등기소 로그인, 결제, 보안문자 처리는 사용자가 직접 수행한다.
7. 세금과 중개보수는 법령상 확정 계산이 아니라 설정값 기반 사전 추정치로 제공한다.

## Tech Stack
- Python 3.13
- 표준 라이브러리 중심 구현
- SQLite: 중복 알림 방지 및 발견 이력 저장
- unittest: 핵심 로직 테스트

## Commands
- Test: `python -m unittest discover -s tests`
- One-shot run: `python -m realestate_alert run-once --config config.example.json`
- Continuous run: `python -m realestate_alert watch --config config.example.json`
- Initialize DB: `python -m realestate_alert init-db --config config.example.json`

## Project Structure
- `realestate_alert/`: 서비스 소스 코드
- `realestate_alert/config.py`: 설정 파일 로딩 및 검증
- `realestate_alert/models.py`: 매물 데이터 모델
- `realestate_alert/filtering.py`: 조건 필터링
- `realestate_alert/store.py`: SQLite 저장소 및 중복 감지
- `realestate_alert/sources.py`: 매물 소스 어댑터
- `realestate_alert/notifiers.py`: 알림 채널
- `realestate_alert/registry.py`: 등기 열람 대상 목록, PDF 분류, 위험 신호 추출
- `realestate_alert/finance.py`: 자기자본 비율, 세금, 중개보수 추정
- `realestate_alert/cli.py`: 실행 명령
- `tests/`: 단위 테스트
- `docs/`: 스펙 및 운영 문서

## Code Style
명확한 데이터 모델과 작은 순수 함수를 우선한다.

```python
def matches_listing(criteria: SearchCriteria, listing: Listing) -> bool:
    if criteria.max_deposit is not None and listing.deposit > criteria.max_deposit:
        return False
    if criteria.required_keywords and not listing.contains_any(criteria.required_keywords):
        return False
    return True
```

## Testing Strategy
- `filtering`은 순수 함수 단위 테스트로 검증한다.
- `store`는 임시 SQLite DB를 사용해 신규/중복 판정을 검증한다.
- `sources`는 로컬 JSON 파일 소스로 먼저 검증한다.
- `registry`는 주소 정리, 위험 키워드 추출, 상태 판정을 검증한다.
- `finance`는 자기자본 비율과 설정값 기반 비용 산출을 검증한다.
- 외부 네트워크 호출은 첫 구현 범위에서 테스트하지 않는다.

## Boundaries
- Always: 설정 오류는 명확한 메시지로 실패한다.
- Always: 이미 알림 보낸 매물은 다시 알리지 않는다.
- Always: 매물 출처, 제목, 가격, 위치, URL을 알림에 포함한다.
- Ask first: 특정 부동산 사이트 크롤링 추가.
- Ask first: 패키지 설치 또는 외부 서비스 가입이 필요한 기능.
- Ask first: 인터넷등기소 자동 로그인/결제/보안문자 처리.
- Never: 계정 로그인 우회, 차단 회피, 비공개 API 무단 호출.
- Never: 텔레그램 토큰 등 비밀값을 저장소에 커밋.
- Never: 추정 세액을 확정 세액처럼 표시.

## Success Criteria
1. 예시 JSON 매물 소스를 읽어 조건에 맞는 신규 매물을 찾는다.
2. 같은 매물은 두 번째 실행에서 중복 알림하지 않는다.
3. 조건 필터링과 중복 감지 테스트가 통과한다.
4. 텔레그램/웹훅 설정이 없어도 콘솔 알림으로 동작한다.
5. `config.example.json`만 보고 사용자가 검색 조건을 수정할 수 있다.
6. 조건 매물 주소를 `registry-targets.csv`로 내보낸다.
7. 사용자가 내려받은 등기 PDF 또는 텍스트 파일에서 위험 권리 키워드를 추출하고 상태를 표시한다.
8. 매입가, 대출액, 현금 투입액, 취득세율, 중개보수율 설정으로 자기자본 비율과 예상 비용을 계산한다.

## Open Questions
1. 실제 검색 대상은 네이버부동산, 직방, 다방, 공공데이터, 직접 관리 파일 중 무엇인가?
2. 알림 채널은 텔레그램, 카카오워크/슬랙 웹훅, 이메일 중 무엇을 우선할 것인가?
3. 필수 조건은 지역, 보증금, 월세, 면적, 권리금, 층수, 병원 용도 가능 여부 중 어디까지인가?
