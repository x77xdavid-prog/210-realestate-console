import unittest
from datetime import date

from realestate_alert.market_price import (
    fetch_commercial_trades,
    recent_deal_months,
    summarize_market,
)

TRADES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<response>
  <header><resultCode>000</resultCode><resultMsg>OK</resultMsg></header>
  <body>
    <items>
      <item>
        <umdNm>목동</umdNm>
        <buildingUse>제2종근린생활시설</buildingUse>
        <landUse>제2종일반주거지역</landUse>
        <dealAmount>250,000</dealAmount>
        <buildingAr>500</buildingAr>
        <plottageAr>250</plottageAr>
        <floor>2</floor>
        <buildYear>2010</buildYear>
        <dealYear>2026</dealYear>
        <dealMonth>5</dealMonth>
        <dealDay>14</dealDay>
        <cdealType></cdealType>
      </item>
      <item>
        <umdNm>목동</umdNm>
        <buildingUse>업무시설</buildingUse>
        <landUse>준주거지역</landUse>
        <dealAmount>100,000</dealAmount>
        <buildingAr>200</buildingAr>
        <plottageAr>100</plottageAr>
        <floor>1</floor>
        <buildYear>2015</buildYear>
        <dealYear>2026</dealYear>
        <dealMonth>4</dealMonth>
        <dealDay>2</dealDay>
        <cdealType>O</cdealType>
      </item>
      <item>
        <umdNm>신정동</umdNm>
        <buildingUse>업무시설</buildingUse>
        <landUse>일반상업지역</landUse>
        <dealAmount>300,000</dealAmount>
        <buildingAr>600</buildingAr>
        <plottageAr>300</plottageAr>
        <floor>3</floor>
        <buildYear>2018</buildYear>
        <dealYear>2026</dealYear>
        <dealMonth>5</dealMonth>
        <dealDay>20</dealDay>
        <cdealType></cdealType>
      </item>
    </items>
  </body>
</response>
"""


class MarketPriceTests(unittest.TestCase):
    def test_parses_trades_and_amount_units(self):
        trades = fetch_commercial_trades("11470", "202605", service_key="k", fetcher=lambda url: TRADES_XML)
        self.assertEqual(len(trades), 3)
        first = trades[0]
        self.assertEqual(first.deal_amount_won, 2_500_000_000)
        self.assertEqual(first.price_per_building_m2, 5_000_000)
        self.assertEqual(first.deal_date, "2026-05-14")
        self.assertTrue(trades[1].canceled)

    def test_summary_filters_dong_and_canceled(self):
        summary = summarize_market(
            "11470", ["202605"], dong="목동", service_key="k", fetcher=lambda url: TRADES_XML
        )
        self.assertEqual(summary.trade_count, 1)
        self.assertEqual(summary.avg_price_per_m2, 5_000_000)
        self.assertEqual(len(summary.recent_trades), 1)

    def test_recent_deal_months_rolls_over_year(self):
        months = recent_deal_months(3, today=date(2026, 1, 15))
        self.assertEqual(months, ["202601", "202512", "202511"])
