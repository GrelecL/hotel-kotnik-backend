from app.services.parser_prompts.cubilis import try_regex_parse

SAMPLE_BODY = """
Reservation Confirmation
Booking Number: CB-123456
Guest: Janez Novak
Arrival: 15.07.2025
Departure: 18.07.2025
Room Type: Double Room
Adults: 2
Children: 1 (age 8)
Board: Breakfast
Total: EUR 360.00
"""


def test_cubilis_regex_parse():
    result = try_regex_parse(SAMPLE_BODY)
    assert result is not None
    assert result["external_ref"] == "CB-123456"
    assert result["guest_name"] == "Janez Novak"
    assert result["checkin"] == "2025-07-15"
    assert result["checkout"] == "2025-07-18"
    assert result["guests_adults"] == 2
    assert result["guests_children"] == 1
    assert result["children_ages"] == [8]
    assert result["board_type"] == "breakfast"
    assert result["price_total"] == 360.0
    assert result["price_currency"] == "EUR"


def test_cubilis_regex_parse_no_match():
    result = try_regex_parse("Hello, how are you?")
    assert result is None
