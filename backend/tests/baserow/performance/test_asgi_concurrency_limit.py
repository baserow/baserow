import asyncio
from asyncio import Semaphore
from asyncio import sleep as asleep
from threading import Event
from time import sleep

from baserow.config.helpers import ConcurrencyLimiterASGI, dummy_context


def test_asgi_concurrency_no_limit(event_loop, test_thread):
    """
    This test ensures that ConcurrencyLimiterASGI will process all requests
    if not limited
    """

    # a pair of events to communicate ()waitevent, setevent,)
    events = [
        (
            Event(),
            Event(),
        )
        for _ in range(10)
    ]
    tasks = []
    eiter = iter(events)
    processed = []
    should_stop = Event()

    async def close_el():
        while True:
            if should_stop.is_set():
                event_loop.stop()
            await asleep(0.001)

    def make_app(qevents):
        async def dummy_app(scope, receive, send):
            waitevent, setevent = next(qevents)
            # mark that we've started the request
            setevent.set()
            out = receive()
            await asleep(0.001)
            # wait to finish
            waitevent.wait(0.1)
            await send(["resp", str(out)])

        return dummy_app

    app = ConcurrencyLimiterASGI(make_app(eiter))
    assert isinstance(app.semaphore, dummy_context)

    app = ConcurrencyLimiterASGI(make_app(eiter), max_concurrency=-1)
    assert isinstance(app.semaphore, dummy_context)

    scope = {}

    def receive():
        return "x"

    async def send(out):
        processed.append(out)

    with test_thread(event_loop.run_forever) as t:
        t.start()
        for _ in events:
            task = asyncio.run_coroutine_threadsafe(
                app(scope, receive, send), event_loop
            )
            tasks.append(task)
        asyncio.run_coroutine_threadsafe(close_el(), event_loop)
        # give it a moment to spin up
        sleep(0.05)
        for waitevent, setevent in events:
            # all requests should be started (setevent set)
            # all should be waiting for waitevent
            assert not waitevent.is_set()
            assert setevent.is_set()
            # let them stop
            waitevent.set()
        sleep(0.01)
        should_stop.set()
        assert len(processed) == len(events)


def test_asgi_concurrency_limit(event_loop, test_thread):
    """
    This test checks if ConcurrencyLimiterASGI will pass x first requests
    when under limitation
    """

    MAX_CONCURRENCY = 3
    # a pair of events to communicate ()waitevent, setevent,)
    events = [
        (
            Event(),
            Event(),
        )
        for _ in range(10)
    ]
    counter = iter(range(10))
    tasks = []
    eiter = iter(events)
    processed = []
    should_stop = Event()

    async def close_el():
        while True:
            if should_stop.is_set():
                event_loop.stop()
            await asleep(0.001)

    def make_app(qevents):
        async def dummy_app(scope, receive, send):
            waitevent, setevent = next(qevents)
            # mark that we've started the request
            setevent.set()
            out = await receive()
            await asleep(0.001)
            # wait to finish
            waitevent.wait(0.5)
            await send(["resp", str(out)])

        return dummy_app

    app = ConcurrencyLimiterASGI(make_app(eiter), max_concurrency=MAX_CONCURRENCY)
    assert isinstance(app.semaphore, Semaphore)

    scope = {}

    async def receive():
        return next(counter)

    async def send(out):
        processed.append(out)

    with test_thread(event_loop.run_forever) as t:
        t.start()
        for _ in events:
            task = asyncio.run_coroutine_threadsafe(
                app(scope, receive, send), event_loop
            )
            tasks.append(task)
        asyncio.run_coroutine_threadsafe(close_el(), event_loop)
        # give it a moment to spin up
        sleep(0.05)
        for idx, _events in enumerate(events):
            waitevent, setevent = _events
            # no request was finished, so all waitevents should not be set
            assert not waitevent.is_set()
            # first MAX_CONCURRENCY setevents should be set
            # as they're allowed by the semaphore
            if idx < MAX_CONCURRENCY:
                assert setevent.is_set()
            else:
                assert not setevent.is_set()
        assert len(processed) == 0

        # allow to finish MAX_CONCURRENCY first requests
        for waitevent, setevent in events[:MAX_CONCURRENCY]:
            waitevent.set()

        sleep(0.01)
        assert len(processed) == MAX_CONCURRENCY

        # so, first MAX_CONCURRENCY are finished
        # and another slice of MAX_CONCURRENCY events are in processing
        # while the rest is waiting
        for idx, _events in enumerate(events):
            waitevent, setevent = _events
            if idx < MAX_CONCURRENCY:
                assert waitevent.is_set()
            else:
                assert not waitevent.is_set()
            # another MAX_CONCURRENCY started
            if idx < MAX_CONCURRENCY * 2:
                assert setevent.is_set()
            else:
                assert not setevent.is_set()
        assert len(processed) == MAX_CONCURRENCY

        for waitevent, setevent in events:
            waitevent.set()
        sleep(0.001)
        should_stop.set()
