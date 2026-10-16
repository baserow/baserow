from unittest.mock import AsyncMock

import pytest
from fakeredis.aioredis import FakeRedis

from baserow.core.chat_runs.buffer import set_buffer_redis
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRunStatus
from baserow.core.chat_runs.registries import ChatRunType, chat_run_type_registry
from baserow.core.chat_runs.types import ChatRunOutcome


@pytest.fixture(autouse=True)
def buffer_redis():
    client = FakeRedis(decode_responses=True)
    set_buffer_redis(client)
    yield client
    set_buffer_redis(None)


class FakeChatRunType(ChatRunType):
    type = "fake"

    def __init__(self):
        super().__init__()
        self.executed = 0
        self.persisted = []
        self.lost_events = []
        self.allow_cancel = True
        self.allow_read = True
        self.warnings_preserved = False

    def can_read(self, user, run):
        return self.allow_read and user.id == run.created_by_id

    def can_cancel(self, user, run):
        return self.allow_cancel and user.id == run.created_by_id

    def can_follow_chat(self, user, chat_id):
        return user.is_authenticated

    async def execute(self, run, journal):
        self.executed += 1
        journal.emit_text("Hello")
        return ChatRunOutcome(ChatRunStatus.COMPLETED, result="Hello")

    def persist_outcome(self, run, outcome):
        self.persisted.append(outcome)
        return {"id": 17, "type": "ai/message", "content": outcome.result}

    def on_run_lost(self, run, events=None):
        self.lost_events.append(events)
        return {"content": "interrupted", "run_status": run.status}

    def ensure_interruption_warning(self, run):
        return self.warnings_preserved


@pytest.fixture
def fake_run_type():
    previous = chat_run_type_registry.registry.copy()
    kind = FakeChatRunType()
    chat_run_type_registry.register(kind)
    yield kind
    chat_run_type_registry.registry = previous


@pytest.fixture
def create_run(data_fixture, fake_run_type):
    def create(chat_id=1, user=None, workspace=None, claim=False, context=None):
        user = user or data_fixture.create_user()
        workspace = workspace or data_fixture.create_workspace(user=user)
        run = ChatRunHandler().create_run(
            "fake",
            chat_id,
            workspace,
            user,
            context or {},
        )
        return ChatRunHandler().claim_run(run.id) if claim else run

    return create


@pytest.fixture
def output_buffer(mocker):
    buffer = mocker.patch("baserow.core.chat_runs.journal.ChatRunBuffer").return_value
    buffer.append = AsyncMock(return_value=[])
    buffer.finish = AsyncMock()
    buffer.invalidate = AsyncMock()
    return buffer
