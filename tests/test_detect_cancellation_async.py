from unittest.mock import AsyncMock
import pytest

from app.services.cancellation_detect import detect_cancellation


@pytest.mark.asyncio
async def test_keyword_match_short_circuits_llm():
    mock_llm = AsyncMock()
    result = await detect_cancellation(
        "cubilis",
        "Reservation Cancelled - Hotel Kotnik",
        "Your booking has been cancelled.",
        llm_client=mock_llm,
    )
    assert result is True
    mock_llm.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_no_keyword_no_llm_returns_false():
    result = await detect_cancellation(
        "cubilis",
        "New Reservation #CB-789",
        "Guest arriving tomorrow, 2 adults.",
    )
    assert result is False


@pytest.mark.asyncio
async def test_llm_fallback_yes():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="YES")
    result = await detect_cancellation(
        "direct_guest",
        "Re: my upcoming stay",
        "I need to change my travel plans unfortunately.",
        llm_client=mock_llm,
    )
    assert result is True
    mock_llm.complete.assert_awaited_once()


@pytest.mark.asyncio
async def test_llm_fallback_no():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="NO")
    result = await detect_cancellation(
        "direct_guest",
        "Re: my upcoming stay",
        "I need to change my travel plans unfortunately.",
        llm_client=mock_llm,
    )
    assert result is False


@pytest.mark.asyncio
async def test_llm_fallback_case_insensitive():
    mock_llm = AsyncMock()
    mock_llm.complete = AsyncMock(return_value="yes, it is a cancellation")
    result = await detect_cancellation(
        "other", "Hello", "Some ambiguous text", llm_client=mock_llm
    )
    assert result is True


@pytest.mark.asyncio
async def test_slovenian_keyword_no_llm_needed():
    result = await detect_cancellation(
        "direct_guest",
        "Odpoved rezervacije",
        "Ne bom prišel, prosim odpovedujem rezervacijo.",
    )
    assert result is True
