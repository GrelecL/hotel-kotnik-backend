FEW_SHOT = """\
Example direct guest email:

Subject: Rezervacija - Novak

Body:
Pozdravljeni,
rad bi rezerviral sobo za 2 odrasli osebi od 10. avgusta do 14. avgusta 2025.
Ime: Marko Novak
Ali imate prosto sobo z zajtrkom?
Lep pozdrav

---

Expected output:
{
  "guest_name": "Marko Novak",
  "checkin": "2025-08-10",
  "checkout": "2025-08-14",
  "room_category": null,
  "guests_adults": 2,
  "guests_children": 0,
  "children_ages": null,
  "board_type": "breakfast",
  "price_total": null,
  "price_currency": "EUR",
  "external_ref": null
}
"""
