from datetime import date
from decimal import Decimal
import pytest

from app.services.tourist_tax import calculate_tourist_tax

RATE = Decimal("2.50")
EXEMPT_AGE = 7
DISCOUNT_PCT = 50


def tax(checkin, checkout, adults, children, ages=None):
    return calculate_tourist_tax(
        date.fromisoformat(checkin),
        date.fromisoformat(checkout),
        adults, children, ages,
        RATE, EXEMPT_AGE, DISCOUNT_PCT,
    )


def test_adults_only():
    # 2 adults, 3 nights = 2 * 3 * 2.50 = 15.00
    assert tax("2025-07-01", "2025-07-04", 2, 0) == Decimal("15.00")


def test_child_exempt():
    # 1 adult + 1 child age 5 (exempt) = 1 * 2 * 2.50 = 5.00
    assert tax("2025-07-01", "2025-07-03", 1, 1, [5]) == Decimal("5.00")


def test_child_discount():
    # 1 adult + 1 child age 10 (50% discount) = (1 + 0.5) * 2 * 2.50 = 7.50
    assert tax("2025-07-01", "2025-07-03", 1, 1, [10]) == Decimal("7.50")


def test_child_adult_age():
    # child aged 18 counts as adult
    assert tax("2025-07-01", "2025-07-03", 1, 1, [18]) == Decimal("10.00")


def test_no_age_data():
    # all children count as adults when no age data
    assert tax("2025-07-01", "2025-07-03", 1, 1, None) == Decimal("10.00")


def test_zero_nights():
    assert tax("2025-07-01", "2025-07-01", 2, 0) == Decimal("0.00")


def test_mixed_children():
    # 1 adult + child 5 (exempt) + child 12 (50%) + child 18 (adult) = (1 + 0 + 0.5 + 1) * 1 * 2.50
    assert tax("2025-07-01", "2025-07-02", 1, 3, [5, 12, 18]) == Decimal("6.25")
