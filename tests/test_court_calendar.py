import json, unittest
from realestate_alert.court_calendar import dates_of, month_counts

def _dxdy(dates):
    return json.dumps({"data": {"dlt_rletDxdySrchLst": [{"dspslDxdyYmd": d} for d in dates]}})

class CalendarTests(unittest.TestCase):
    def test_dates_of_dedupes_sorted(self):
        out = dates_of("B000210", fetcher=lambda b: _dxdy(["20260625", "20260623", "20260623"]))
        self.assertEqual(out, ["20260623", "20260625"])

    def test_dates_of_absorbs_error(self):
        def boom(b): raise RuntimeError("x")
        self.assertEqual(dates_of("B000210", fetcher=boom), [])

    def test_month_counts_aggregates(self):
        dmap = {"서울중앙": ["20260623"], "서울서부": ["20260623", "20260630"]}
        counts = month_counts(
            courts=list(dmap),
            dates_fetcher=lambda c: dmap[c],
            count_fetcher=lambda c, ymd: 10,
        )
        self.assertEqual(counts["20260623"]["서울중앙"], 10)
        self.assertEqual(counts["20260623"]["__total__"], 20)
        self.assertEqual(counts["20260630"]["__total__"], 10)
