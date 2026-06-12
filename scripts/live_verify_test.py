"""양 키 등록 후 전체 검증 파이프라인 라이브 테스트 (일회성 점검용)."""
from realestate_alert.verify import verify_address

report = verify_address("서울 양천구 목동 917-9", market_months=3)
building = report.get("building") or {}
land = report.get("land") or {}
market = report.get("market") or {}

print("=== 건축물대장 ===")
print("건물명:", building.get("building_name") or "(무명)", "/ 주용도:", building.get("main_purpose"))
print("대지/연면적:", building.get("plat_area_m2"), "/", building.get("total_area_m2"), "㎡")
print(
    "층수: 지상", building.get("ground_floors"), "지하", building.get("underground_floors"),
    "/ 주차:", building.get("parking_spaces"), "대 / 승강기:", building.get("elevator_count"), "대",
)
print(
    "사용승인:", building.get("approval_date"),
    "/ 건폐율:", building.get("building_coverage_ratio"), "% / 용적률:", building.get("floor_area_ratio"), "%",
)
print("=== 토지 ===")
print("용도지역:", land.get("zoning_names"))
print("도로접면:", land.get("road_side"), "/", land.get("road_width_hint_m"), "m")
print("공시지가:", land.get("official_price_per_m2"), "원/㎡", land.get("official_price_year"), "년")
print("=== 실거래 (최근 3개월 목동 상업업무용) ===")
print("거래:", market.get("trade_count"), "건 / ㎡당 평균:", market.get("avg_price_per_m2"))
for trade in (market.get("recent_trades") or [])[:3]:
    print(" -", trade["deal_date"], trade["building_use"], f"{trade['deal_amount_won']:,}원", trade["building_area_m2"], "㎡")
print("=== 오류 ===", report["errors"])
