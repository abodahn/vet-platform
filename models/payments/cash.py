# -*- coding: utf-8 -*-
"""Methods the clinic collects itself: cash, a card on the counter terminal,
a bank transfer, an Instapay push.

Cash leads because it is how most Egyptian veterinary clinics are actually paid,
it needs no configuration, and it keeps working when the internet does not.

They share one class because they are the same transaction from the app's point
of view: a human already moved the money and the app records it. What differs is
only the label that reaches the ledger and the receipt — and that label matters,
because "which of today's takings were card and which were cash" is the question
a clinic reconciles its drawer with every evening.

"Cash on delivery" and "cash at the counter" are the same thing here.
"""
from decimal import Decimal

from models.payments import Gateway, SUCCEEDED


class CounterGateway(Gateway):
    """Money collected by staff. The app is the record, not the mover."""

    offline = True

    def __init__(self, name: str, label: str, label_ar: str, prefix: str):
        self.name = name
        self.label = label
        self.label_ar = label_ar
        self._prefix = prefix

    def configured(self) -> bool:
        return True

    def charge(self, intent: dict) -> dict:
        # The money is already in the drawer. The value here is the trail: who
        # took it and when, which is what a shift-end discrepancy is settled
        # with, and what add_payment recorded nowhere.
        return {"status": SUCCEEDED,
                "gateway_ref": f"{self._prefix}-{intent['id']}",
                "detail": f"{self.label} received by staff"}

    def refund(self, intent: dict, amount: Decimal) -> dict:
        return {"status": SUCCEEDED,
                "gateway_ref": f"{self._prefix}REF-{intent['id']}",
                "detail": f"Refunded via {self.label}"}


def CashGateway() -> CounterGateway:
    return CounterGateway("cash", "Cash", "نقدي", "CASH")


def counter_gateways() -> list:
    """Every over-the-counter method, cash first."""
    return [
        CashGateway(),
        CounterGateway("card", "Card (terminal)", "بطاقة (ماكينة)", "CARD"),
        CounterGateway("transfer", "Bank transfer", "تحويل بنكي", "TRF"),
        CounterGateway("instapay", "InstaPay", "إنستاباي", "IPAY"),
        # The invoice screen has always offered Insurance. Without it here the
        # alias lookup fell through to cash and the ledger recorded an insurer
        # settlement as a cash payment — money the clinic would then look for
        # in a drawer it was never in.
        CounterGateway("insurance", "Insurance", "تأمين", "INS"),
    ]
