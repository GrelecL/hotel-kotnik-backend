from app.services.parser import detect_source
from app.models.reservation import ReservationSource


def test_detect_cubilis_domain():
    assert detect_source("noreply@cubilis.eu", "New Reservation") == ReservationSource.cubilis


def test_detect_booking_domain():
    assert detect_source("partner@booking.com", "New reservation") == ReservationSource.booking


def test_detect_booking_subject():
    assert detect_source("info@someota.com", "New reservation - Booking.com") == ReservationSource.booking


def test_detect_cubilis_subject():
    assert detect_source("mail@hotel.si", "Cubilis reservation #123") == ReservationSource.cubilis


def test_detect_other():
    assert detect_source("guest@gmail.com", "Rezervacija za julij") == ReservationSource.other
