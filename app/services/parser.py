import json
import logging
import re
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.models.reservation import ReservationSource
from app.services.parser_prompts.base import SYSTEM_PROMPT
from app.services.parser_prompts import cubilis as cubilis_prompts
from app.services.parser_prompts import booking as booking_prompts
from app.services.parser_prompts import generic as generic_prompts

logger = logging.getLogger(__name__)

_SOURCE_FEW_SHOTS = {
    ReservationSource.cubilis: cubilis_prompts.FEW_SHOT,
    ReservationSource.booking: booking_prompts.FEW_SHOT,
    ReservationSource.direct_guest: generic_prompts.FEW_SHOT,
    ReservationSource.walk_in: generic_prompts.FEW_SHOT,
    ReservationSource.other: generic_prompts.FEW_SHOT,
}

_FROM_DOMAIN_MAP = {
    "cubilis.com": ReservationSource.cubilis,
    "cubilis.eu": ReservationSource.cubilis,
    "booking.com": ReservationSource.booking,
    "partner.booking.com": ReservationSource.booking,
}

_SUBJECT_PATTERNS = [
    (re.compile(r"cubilis", re.IGNORECASE), ReservationSource.cubilis),
    (re.compile(r"booking\.com", re.IGNORECASE), ReservationSource.booking),
]


def detect_source(from_addr: str, subject: str) -> ReservationSource:
    for domain, source in _FROM_DOMAIN_MAP.items():
        if domain in from_addr.lower():
            return source
    for pattern, source in _SUBJECT_PATTERNS:
        if pattern.search(subject):
            return source
    return ReservationSource.other


async def _call_llm(source: ReservationSource, subject: str, body: str) -> dict | None:
    few_shot = _SOURCE_FEW_SHOTS.get(source, generic_prompts.FEW_SHOT)
    user_content = (
        f"{few_shot}\n\n"
        f"Now extract from this email:\n\n"
        f"Subject: {subject}\n\n"
        f"Body:\n{body[:6000]}"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "https://hotel-kotnik.local",
                "X-Title": "Hotel Kotnik Reservation Parser",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0,
                "max_tokens": 512,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences if present
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON: %s", content[:200])
        return None


async def parse_email(
    source: ReservationSource,
    subject: str,
    body: str,
) -> dict | None:
    """
    Returns parsed dict or None on failure.
    Tries regex fast-path for Cubilis; falls back to LLM.
    """
    if source == ReservationSource.cubilis:
        result = cubilis_prompts.try_regex_parse(body)
        if result:
            logger.debug("Cubilis regex parse succeeded")
            return result

    result = await _call_llm(source, subject, body)
    return result
