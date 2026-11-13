import pytest

from baserow.contrib.agent.triggers.overlap import OverlapLimits, get_overlap_limits


@pytest.mark.parametrize(
    "on_overlap,queued_cap,parallel_cap,limits",
    [
        ("skip", 10, 5, OverlapLimits(max_going=1, max_queued=0)),
        ("wait", 10, 5, OverlapLimits(max_going=1, max_queued=10)),
        ("parallel", 10, 5, OverlapLimits(max_going=5, max_queued=10)),
        ("wait", 0, 5, OverlapLimits(max_going=1, max_queued=None)),
        ("parallel", -1, 0, OverlapLimits(max_going=None, max_queued=None)),
    ],
)
def test_each_overlap_rule_sets_how_many_replies_go_and_queue(
    settings, on_overlap, queued_cap, parallel_cap, limits
):
    settings.AGENT_TRIGGER_MAX_QUEUED_RUNS = queued_cap
    settings.AGENT_TRIGGER_MAX_PARALLEL_RUNS = parallel_cap

    assert get_overlap_limits(on_overlap) == limits


def test_limits_tell_whether_one_more_reply_goes_or_queues():
    limited, unlimited = OverlapLimits(2, 0), OverlapLimits(None, None)

    assert [limited.has_room_to_go(going) for going in (1, 2)] == [True, False]
    assert [limited.room_to_go(going) for going in (0, 2, 3)] == [2, 0, 0]
    assert limited.has_room_to_queue(0) is False
    assert unlimited.has_room_to_go(1000) and unlimited.has_room_to_queue(1000)
    assert unlimited.room_to_go(1000) is None
