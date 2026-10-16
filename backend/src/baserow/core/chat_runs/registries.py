from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import AbstractUser

from baserow.core.registry import Instance, Registry

from .models import ChatRun
from .types import ChatRunOutcome

if TYPE_CHECKING:
    from .journal import ChatRunJournal


class ChatRunType(Instance):
    """Product permissions, execution and durable conversation persistence."""

    def can_read(self, user: AbstractUser, run: ChatRun) -> bool:
        raise NotImplementedError

    def can_cancel(self, user: AbstractUser, run: ChatRun) -> bool:
        raise NotImplementedError

    def can_follow_chat(self, user: AbstractUser, chat_id: int) -> bool:
        raise NotImplementedError

    async def execute(self, run: ChatRun, journal: "ChatRunJournal") -> ChatRunOutcome:
        """Execute once; drain active tools when the journal requests Stop."""

        raise NotImplementedError

    def persist_outcome(self, run: ChatRun, outcome: ChatRunOutcome) -> dict | None:
        """Save answer/history in the transaction that ends the locked run."""

        return None

    def serialize_outcome(self, run: ChatRun) -> dict | None:
        """Return the durable result without consulting the temporary buffer."""

        return run.outcome

    def on_run_lost(
        self, run: ChatRun, events: list[dict[str, Any]] | None = None
    ) -> dict | None:
        """Save an interrupted turn, optionally using complete retained output."""

        return None

    def on_run_not_started(self, run: ChatRun) -> dict | None:
        """Save the outcome of work which provably never started."""

        return None

    def ensure_interruption_warning(self, run: ChatRun) -> bool:
        """Before pruning an incomplete run, preserve its warning in the product.

        Returning False keeps the run available for the next request's history
        reconstruction, including when an earlier persistence hook failed.
        """

        return False


class ChatRunTypeRegistry(Registry[ChatRunType]):
    name = "chat_run_type"


chat_run_type_registry = ChatRunTypeRegistry()
