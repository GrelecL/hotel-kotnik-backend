FEW_SHOT = """\
Example Cubilis reservation email:

Subject: New Reservation #CB-123456 - Hotel Kotnik

Body:
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

---

Expected output:
{
  "guest_name": "Janez Novak",
  "checkin": "2025-07-15",
  "checkout": "2025-07-18",
  "room_category": "Double Room",
  "guests_adults": 2,
  "guests_children": 1,
  "children_ages": [8],
  "board_type": "breakfast",
  "price_total": 360.00,
  "price_currency": "EUR",
  "external_ref": "CB-123456"
}
"""

# Regex patterns for fast path (Cubilis format is stable)
import re

PATTERNS = {
    "external_ref": re.compile(r"Booking Number[:\s]+([A-Z0-9\-]+)", re.IGNORECASE),
    "guest_name": re.compile(r"Guest[:\s]+(.+)", re.IGNORECASE),
    "checkin": re.compile(r"Arrival[:\s]+(\d{1,2}[\.\/]\d{1,2}[\.\/]\d{4})", re.IGNORECASE),
    "checkout": re.compile(r"Departure[:\s]+(\d{1,2}[\.\/]\d{1,2}[\.\/]\d{4})", re.IGNORECASE),
    "room_category": re.compile(r"Room Type[:\s]+(.+)", re.IGNORECASE),
    "guests_adults": re.compile(r"Adults[:\s]+(\d+)", re.IGNORECASE),
    "guests_children": re.compile(r"Children[:\s]+(\d+)", re.IGNORECASE),
    "price_total": re.compile(r"Total[:\s]+(?:EUR\s*)?([\d,\.]+)", re.IGNORECASE),
}

CHILDREN_AGE_PATTERN = re.compile(r"age[s]?\s+([\d,\s]+)", re.IGNORECASE)


def _parse_date(raw: str) -> str | None:
    """Convert dd.mm.yyyy or dd/mm/yyyy -> yyyy-mm-dd."""
    raw = raw.strip()
    for sep in (".", "/"):
        parts = raw.split(sep)
        if len(parts) == 3:
            d, m, y = parts
            try:
                return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            except ValueError:
                pass
    return None


def try_regex_parse(body: str) -> dict | None:
    result = {}
    for field, pattern in PATTERNS.items():
        m = pattern.search(body)
        result[field] = m.group(1).strip() if m else None

    if not result.get("guest_name") or not result.get("checkin"):
        return None

    result["checkin"] = _parse_date(result["checkin"]) if result["checkin"] else None
    result["checkout"] = _parse_date(result["checkout"]) if result["checkout"] else None

    for int_field in ("guests_adults", "guests_children"):
        try:
            result[int_field] = int(result[int_field]) if result[int_field] else None
        except ValueError:
            result[int_field] = None

    try:
        raw_price = result.get("price_total", "").replace(",", ".")
        result["price_total"] = float(raw_price) if raw_price else None
    except (ValueError, AttributeError):
        result["price_total"] = None

    result["price_currency"] = "EUR"

    # Extract children ages from body
    age_match = CHILDREN_AGE_PATTERN.search(body)
    if age_match:
        ages_raw = age_match.group(1)
        ages = [int(a.strip()) for a in re.split(r"[,\s]+", ages_raw) if a.strip().isdigit()]
        result["children_ages"] = ages if ages else None
    else:
        result["children_ages"] = None

    # Board type mapping
    board_raw = body.lower()
    if "full board" in board_raw or "polni penzion" in board_raw:
        result["board_type"] = "full_board"
    elif "half board" in board_raw or "polpenzion" in board_raw:
        result["board_type"] = "half_board"
    elif "breakfast" in board_raw or "zajtrk" in board_raw:
        result["board_type"] = "breakfast"
    else:
        result["board_type"] = "none"

    return result
