FEW_SHOT = """\
Example Booking.com reservation email:

Subject: New reservation - Booking.com (Reservation no.: 1234567890)

Body:
You have a new reservation!
Reservation number: 1234567890
Guest name: Maria Schmidt
Check-in: Friday, 20 June 2025 (from 14:00)
Check-out: Sunday, 22 June 2025 (until 11:00)
Number of guests: 2 adults
Room: Superior Double Room
Meal plan: Breakfast included
Total price: EUR 240.00

---

Expected output:
{
  "guest_name": "Maria Schmidt",
  "checkin": "2025-06-20",
  "checkout": "2025-06-22",
  "room_category": "Superior Double Room",
  "guests_adults": 2,
  "guests_children": 0,
  "children_ages": null,
  "board_type": "breakfast",
  "price_total": 240.00,
  "price_currency": "EUR",
  "external_ref": "1234567890"
}
"""
