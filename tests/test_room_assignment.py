"""
Unit tests for room_assignment logic without a real DB.
We test the SQL construction and the "no room found" path
by mocking the session.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date

from app.services.room_assignment import find_available_room


@pytest.mark.asyncio
async def test_returns_room_when_found():
    from app.models.room import Room

    mock_room = Room(id=5, number="101", floor=1, category_id=2)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_room

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    room = await find_available_room(db, category_id=2, checkin=date(2025, 7, 1), checkout=date(2025, 7, 4))
    assert room is mock_room
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_returns_none_when_no_room():
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=mock_result)

    room = await find_available_room(db, category_id=99, checkin=date(2025, 7, 1), checkout=date(2025, 7, 4))
    assert room is None
