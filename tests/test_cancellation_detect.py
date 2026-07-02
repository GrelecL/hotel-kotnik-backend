import pytest
from app.services.cancellation_detect import is_cancellation_by_keywords


def test_cubilis_cancellation():
    assert is_cancellation_by_keywords(
        "cubilis",
        "Reservation Cancelled - Hotel Kotnik",
        "Your booking has been cancelled.",
    )


def test_booking_cancellation():
    assert is_cancellation_by_keywords(
        "booking",
        "Your reservation has been cancelled",
        "The guest has cancelled their reservation.",
    )


def test_not_cancellation():
    assert not is_cancellation_by_keywords(
        "cubilis",
        "New Reservation #CB-123456",
        "Guest: Janez Novak. Arrival: 15.07.2025",
    )


def test_slovenian_cancellation():
    assert is_cancellation_by_keywords(
        "direct_guest",
        "Odpoved rezervacije",
        "Ne bom prišel, prosim odpovedujem rezervacijo.",
    )
