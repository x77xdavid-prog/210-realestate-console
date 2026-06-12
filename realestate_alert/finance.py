from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PurchaseEstimateInput:
    purchase_price: int
    loan_amount: int
    cash_available: int
    acquisition_tax_rate: float
    brokerage_rate: float
    legal_fee: int = 0
    other_costs: int = 0


@dataclass(frozen=True)
class PurchaseEstimate:
    equity_amount: int
    equity_ratio: float
    acquisition_tax: int
    brokerage_fee: int
    legal_fee: int
    other_costs: int
    total_cash_needed: int
    cash_gap: int
    note: str


def estimate_purchase(data: PurchaseEstimateInput) -> PurchaseEstimate:
    if data.purchase_price <= 0:
        raise ValueError("purchase_price must be greater than zero.")
    if data.loan_amount < 0 or data.cash_available < 0:
        raise ValueError("loan_amount and cash_available must not be negative.")
    if data.loan_amount > data.purchase_price:
        raise ValueError("loan_amount must not exceed purchase_price.")

    equity_amount = data.purchase_price - data.loan_amount
    acquisition_tax = round(data.purchase_price * data.acquisition_tax_rate)
    brokerage_fee = round(data.purchase_price * data.brokerage_rate)
    total_cash_needed = equity_amount + acquisition_tax + brokerage_fee + data.legal_fee + data.other_costs
    return PurchaseEstimate(
        equity_amount=equity_amount,
        equity_ratio=equity_amount / data.purchase_price,
        acquisition_tax=acquisition_tax,
        brokerage_fee=brokerage_fee,
        legal_fee=data.legal_fee,
        other_costs=data.other_costs,
        total_cash_needed=total_cash_needed,
        cash_gap=max(0, total_cash_needed - data.cash_available),
        note="세금과 중개보수는 설정값 기반 추정치입니다. 실제 취득 전 최신 법령과 전문가 검토가 필요합니다.",
    )
