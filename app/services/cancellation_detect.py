import re
from app.models.reservation import ReservationSource

# Per-source cancellation keywords (subject + body)
SOURCE_KEYWORDS: dict[str, list[str]] = {
    ReservationSource.cubilis: [
        "cancellation", "cancelled", "canceled", "storno", "annulering",
        "rezervacija preklicana", "booking cancelled",
    ],
    ReservationSource.booking: [
        "cancellation", "cancelled", "canceled", "your reservation has been cancelled",
        "booking has been cancelled", "guest has cancelled",
    ],
    ReservationSource.direct_guest: [
        "cancel", "odpoved", "storno", "preklicati", "ne bom prišel",
        "ne pridemo", "odpovedujem",
    ],
    ReservationSource.walk_in: [],
    ReservationSource.other: [
        "cancel", "cancellation", "storno", "odpoved",
    ],
}

_GENERIC_KEYWORDS = ["cancell", "cancel", "storno", "annul", "odpoved", "preklicana"]


def _keyword_match(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def is_cancellation_by_keywords(
    source: str,
    subject: str,
    body: str,
) -> bool:
    combined = f"{subject} {body}"
    source_kws = SOURCE_KEYWORDS.get(source, [])
    if source_kws and _keyword_match(combined, source_kws):
        return True
    return _keyword_match(combined, _GENERIC_KEYWORDS)


async def is_cancellation_by_llm(
    source: str,
    subject: str,
    body: str,
    llm_client,
) -> bool:
    """LLM fallback for ambiguous cases."""
    prompt = (
        "You are a hotel reservation system. "
        "Determine if the following email is a CANCELLATION of a reservation. "
        "Reply with exactly one word: YES or NO.\n\n"
        f"Source: {source}\n"
        f"Subject: {subject}\n\n"
        f"Body:\n{body[:3000]}"
    )
    response = await llm_client.complete(prompt, max_tokens=5)
    return response.strip().upper().startswith("YES")


async def detect_cancellation(
    source: str,
    subject: str,
    body: str,
    llm_client=None,
) -> bool:
    if is_cancellation_by_keywords(source, subject, body):
        return True
    if llm_client is not None:
        return await is_cancellation_by_llm(source, subject, body, llm_client)
    return False
