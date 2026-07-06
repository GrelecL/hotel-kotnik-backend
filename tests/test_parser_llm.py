from unittest.mock import patch, AsyncMock, MagicMock
import httpx
import pytest

from app.services.parser import _call_llm, parse_email
from app.models.reservation import ReservationSource

VALID_JSON = (
    '{"guest_name": "Janez Novak", "checkin": "2025-07-10", '
    '"checkout": "2025-07-15", "guests_adults": 2, "guests_children": 0}'
)
VALID_JSON_FENCED = f"```json\n{VALID_JSON}\n```"


def _mock_resp(content: str):
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def _patch_async_client(mock_resp):
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)
    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=mock_client)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=ctx_mgr)


@pytest.mark.asyncio
async def test_call_llm_returns_parsed_dict():
    with _patch_async_client(_mock_resp(VALID_JSON)):
        result = await _call_llm(ReservationSource.other, "Subject", "Body")
    assert result is not None
    assert result["guest_name"] == "Janez Novak"
    assert result["checkin"] == "2025-07-10"


@pytest.mark.asyncio
async def test_call_llm_strips_markdown_fences():
    with _patch_async_client(_mock_resp(VALID_JSON_FENCED)):
        result = await _call_llm(ReservationSource.other, "Subject", "Body")
    assert result is not None
    assert result["checkout"] == "2025-07-15"


@pytest.mark.asyncio
async def test_call_llm_returns_none_on_http_error():
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
    ctx_mgr = AsyncMock()
    ctx_mgr.__aenter__ = AsyncMock(return_value=mock_client)
    ctx_mgr.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=ctx_mgr):
        result = await _call_llm(ReservationSource.other, "Subject", "Body")
    assert result is None


@pytest.mark.asyncio
async def test_call_llm_returns_none_on_invalid_json():
    with _patch_async_client(_mock_resp("not json at all")):
        result = await _call_llm(ReservationSource.other, "Subject", "Body")
    assert result is None


@pytest.mark.asyncio
async def test_parse_email_cubilis_regex_fast_path():
    body = """
Reservation Confirmation
Booking Number: CB-123456
Guest: Janez Novak
Arrival: 15.07.2025
Departure: 18.07.2025
Room Type: Double Room
Adults: 2
Children: 0
Board: Breakfast
Total: EUR 180.00
"""
    with patch("app.services.parser._call_llm", new_callable=AsyncMock) as mock_llm:
        result = await parse_email(ReservationSource.cubilis, "New Booking CB-123456", body)
    mock_llm.assert_not_called()
    assert result is not None
    assert result["external_ref"] == "CB-123456"


@pytest.mark.asyncio
async def test_parse_email_non_cubilis_calls_llm():
    with patch("app.services.parser._call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"guest_name": "Test"}
        result = await parse_email(ReservationSource.booking, "Subject", "Body")
    mock_llm.assert_awaited_once()
    assert result == {"guest_name": "Test"}


@pytest.mark.asyncio
async def test_parse_email_cubilis_falls_back_to_llm_on_regex_miss():
    with patch("app.services.parser._call_llm", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {"guest_name": "Fallback"}
        result = await parse_email(ReservationSource.cubilis, "Subject", "no match body")
    mock_llm.assert_awaited_once()
    assert result == {"guest_name": "Fallback"}
