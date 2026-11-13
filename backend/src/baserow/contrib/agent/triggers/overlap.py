from dataclasses import dataclass

from django.conf import settings

from baserow.contrib.agent.models import AgentTrigger


@dataclass(frozen=True)
class OverlapLimits:
    """
    How many replies of one trigger may be going and queued at once, by its
    overlap rule. None means no limit; the rate limits and the workspace's run
    limit still apply.

    ========  ==================  ===============
    Rule      Going (P)           Queued (Q)
    ========  ==================  ===============
    skip      1                   0
    wait      1                   the queue cap
    parallel  the parallel cap    the queue cap
    ========  ==================  ===============

    A firing starts when fewer than P replies are going and nothing is queued
    ahead of it, queues when fewer than Q are queued, and is skipped otherwise.
    """

    max_going: int | None
    max_queued: int | None

    def has_room_to_go(self, going: int) -> bool:
        """
        :param going: How many replies of the trigger are going.
        :return: Whether one more may start.
        """

        return self.max_going is None or going < self.max_going

    def room_to_go(self, going: int) -> int | None:
        """
        :param going: How many replies of the trigger are going.
        :return: How many more may start, or None when there is no limit.
        """

        return None if self.max_going is None else max(self.max_going - going, 0)

    def has_room_to_queue(self, queued: int) -> bool:
        """
        :param queued: How many replies of the trigger are queued.
        :return: Whether one more may queue.
        """

        return self.max_queued is None or queued < self.max_queued


def _cap(value: int) -> int | None:
    """
    :param value: A configured cap.
    :return: The cap, or None when it is 0 or less, which means no limit.
    """

    return value if value > 0 else None


def get_overlap_limits(on_overlap: str) -> OverlapLimits:
    """
    :param on_overlap: The trigger's overlap rule, one of ``AgentTrigger.OnOverlap``.
    :return: The limits the rule sets on its replies.
    """

    if on_overlap == AgentTrigger.OnOverlap.SKIP:
        return OverlapLimits(max_going=1, max_queued=0)
    queue_cap = _cap(settings.AGENT_TRIGGER_MAX_QUEUED_RUNS)
    if on_overlap == AgentTrigger.OnOverlap.PARALLEL:
        return OverlapLimits(
            max_going=_cap(settings.AGENT_TRIGGER_MAX_PARALLEL_RUNS),
            max_queued=queue_cap,
        )
    return OverlapLimits(max_going=1, max_queued=queue_cap)
