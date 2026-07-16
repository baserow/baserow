import pytest

from baserow.config.helpers import BaserowASGIHandler


@pytest.mark.asyncio
async def test_listen_for_disconnect_returns_instead_of_raising():
    handler = BaserowASGIHandler.__new__(BaserowASGIHandler)

    async def receive():
        return {"type": "http.disconnect"}

    assert await handler.listen_for_disconnect(receive) is None


@pytest.mark.asyncio
async def test_listen_for_disconnect_still_asserts_on_invalid_message():
    handler = BaserowASGIHandler.__new__(BaserowASGIHandler)

    async def receive():
        return {"type": "http.unexpected"}

    with pytest.raises(AssertionError):
        await handler.listen_for_disconnect(receive)
