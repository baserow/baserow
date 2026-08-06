import pytest

from baserow.core.deferred_callbacks import (
    deferred_callback_context,
    register_deferred_callback,
)


def test_callbacks_run_when_the_context_exits():
    ran = []

    with deferred_callback_context():
        register_deferred_callback(lambda: ran.append("first"))
        register_deferred_callback(lambda: ran.append("second"))
        assert ran == [], "nothing may run before the context exits"

    assert ran == ["first", "second"]


def test_the_register_alias_on_the_context():
    ran = []

    with deferred_callback_context():
        deferred_callback_context.register(lambda: ran.append("x"))

    assert ran == ["x"]


def test_registering_outside_a_context_is_refused():
    with pytest.raises(RuntimeError):
        register_deferred_callback(lambda: None)


def test_a_nested_context_defers_to_the_outermost_one():
    """An import that runs inside a larger one must not run its deferred work
    early: the outer import is what completes the id mapping."""

    ran = []

    with deferred_callback_context():
        with deferred_callback_context():
            register_deferred_callback(lambda: ran.append("inner"))
        assert ran == [], "the inner context must not run anything"
        register_deferred_callback(lambda: ran.append("outer"))

    assert ran == ["inner", "outer"]


def test_a_callback_can_register_more_work():
    """How a deferred import defers again: the action import waits for every
    application, and its formula remapping waits for every action."""

    ran = []

    def outer():
        ran.append("outer")
        register_deferred_callback(inner)

    def inner():
        ran.append("inner")

    with deferred_callback_context():
        register_deferred_callback(outer)
        register_deferred_callback(lambda: ran.append("sibling"))

    assert ran == ["outer", "sibling", "inner"]


def test_nothing_runs_when_the_block_raised():
    """A failed import leaves half-imported rows behind, which is nothing to
    run the deferred work against."""

    ran = []

    with pytest.raises(ValueError):
        with deferred_callback_context():
            register_deferred_callback(lambda: ran.append("x"))
            raise ValueError("import failed")

    assert ran == []


def test_a_failed_block_leaves_no_context_behind():
    with pytest.raises(ValueError):
        with deferred_callback_context():
            raise ValueError("import failed")

    with pytest.raises(RuntimeError):
        register_deferred_callback(lambda: None)


def test_a_raising_callback_leaves_no_context_behind():
    def boom():
        raise ValueError("callback failed")

    with pytest.raises(ValueError):
        with deferred_callback_context():
            register_deferred_callback(boom)

    with pytest.raises(RuntimeError):
        register_deferred_callback(lambda: None)


def test_a_second_context_starts_empty():
    ran = []

    with deferred_callback_context():
        register_deferred_callback(lambda: ran.append("first"))

    with deferred_callback_context():
        register_deferred_callback(lambda: ran.append("second"))

    assert ran == ["first", "second"], "a callback must never run twice"
