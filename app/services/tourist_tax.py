from decimal import Decimal
from datetime import date


def calculate_tourist_tax(
    checkin: date,
    checkout: date,
    guests_adults: int,
    guests_children: int,
    children_ages: list[int] | None,
    tax_rate: Decimal,
    child_exempt_age: int,
    child_discount_pct: int,
) -> Decimal:
    nights = (checkout - checkin).days
    if nights <= 0:
        return Decimal("0.00")

    if children_ages is not None:
        adult_equivalent = Decimal(str(guests_adults))
        for age in children_ages:
            if age < child_exempt_age:
                continue
            elif age <= 17:
                adult_equivalent += Decimal(str(child_discount_pct)) / Decimal("100")
            else:
                adult_equivalent += Decimal("1")
    else:
        # No age data - count all as adults; reception corrects manually
        adult_equivalent = Decimal(str(guests_adults + guests_children))

    total = Decimal(str(nights)) * tax_rate * adult_equivalent
    return total.quantize(Decimal("0.01"))
