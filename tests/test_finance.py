import unittest

from realestate_alert.finance import PurchaseEstimateInput, estimate_purchase


class FinanceTests(unittest.TestCase):
    def test_estimates_equity_ratio_taxes_brokerage_and_total_cash_needed(self):
        estimate = estimate_purchase(
            PurchaseEstimateInput(
                purchase_price=1_000_000_000,
                loan_amount=600_000_000,
                cash_available=450_000_000,
                acquisition_tax_rate=0.046,
                brokerage_rate=0.009,
                legal_fee=2_000_000,
                other_costs=3_000_000,
            )
        )

        self.assertEqual(estimate.equity_amount, 400_000_000)
        self.assertEqual(estimate.equity_ratio, 0.4)
        self.assertEqual(estimate.acquisition_tax, 46_000_000)
        self.assertEqual(estimate.brokerage_fee, 9_000_000)
        self.assertEqual(estimate.total_cash_needed, 460_000_000)
        self.assertEqual(estimate.cash_gap, 10_000_000)
