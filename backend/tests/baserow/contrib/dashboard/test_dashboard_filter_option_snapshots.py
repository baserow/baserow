from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

from django.core import signing

import pytest
from freezegun import freeze_time

from baserow.contrib.dashboard.filters.exceptions import DashboardFilterOptionsExpired
from baserow.contrib.dashboard.filters.option_snapshots import (
    DashboardFilterOptionsSnapshot,
)


@pytest.fixture
def option_snapshot():
    snapshot = DashboardFilterOptionsSnapshot(
        SimpleNamespace(pk=uuid4().hex),
        SimpleNamespace(pk=1, formula_value={"value": "'Alpha,Beta,Gamma'"}),
    )
    yield snapshot
    keys = list(snapshot.redis.scan_iter(match=f"{snapshot.prefix}:*"))
    if keys:
        snapshot.redis.delete(*keys)


def test_selected_option_membership_checks_distinct_values_once(
    option_snapshot, monkeypatch
):
    cursor = option_snapshot.create(lambda: ["Alpha", "Beta", "Gamma"], [])
    commands = []
    original_pipeline = option_snapshot.redis.pipeline

    def counted_pipeline(*args, **kwargs):
        pipeline = original_pipeline(*args, **kwargs)
        execute = pipeline.execute

        def counted_execute(*args, **kwargs):
            commands.extend(command for command, _ in pipeline.command_stack)
            return execute(*args, **kwargs)

        monkeypatch.setattr(pipeline, "execute", counted_execute)
        return pipeline

    monkeypatch.setattr(option_snapshot.redis, "pipeline", counted_pipeline)
    page = option_snapshot.page(
        cursor,
        limit=1,
        selected=["Gamma", "missing", "Alpha", "Gamma", "Alpha", "missing"],
        validate_tables=lambda _: None,
    )

    assert page["results"] == ["Alpha"]
    assert page["available"] == ["Gamma", "Alpha"]
    assert [command[2] for command in commands if command[0] == "ZSCORE"] == [
        "Gamma",
        "missing",
        "Alpha",
    ]


def test_independent_option_snapshots_expire_without_extending_on_read(option_snapshot):
    cursor = option_snapshot.create(lambda: ["Alpha", "Beta", "Gamma"], [])
    second = option_snapshot.create(lambda: ["Updated"], [])

    first_page = option_snapshot.page(
        cursor, limit=1, selected=[], validate_tables=lambda _: None
    )
    assert first_page["results"] == ["Alpha"]
    assert option_snapshot.page(
        second, limit=1, selected=[], validate_tables=lambda _: None
    )["results"] == ["Updated"]
    keys = list(option_snapshot.redis.scan_iter(match=f"{option_snapshot.prefix}:*"))
    for key in keys:
        assert 0 < option_snapshot.redis.ttl(key) <= option_snapshot.lifetime
        option_snapshot.redis.expire(key, 30)

    assert option_snapshot.page(
        first_page["next"], limit=1, selected=[], validate_tables=lambda _: None
    )["results"] == ["Beta"]
    for key in keys:
        assert 0 < option_snapshot.redis.ttl(key) <= 30


def test_identical_option_snapshots_reuse_stored_values(option_snapshot):
    values = [f"{index:04d}" + "x" * 1020 for index in range(100)]
    cursors = [
        option_snapshot.create(lambda: values * (1 + index % 2), [17])
        for index in range(8)
    ]

    keys = option_snapshot.redis.scan_iter(match=f"{option_snapshot.prefix}:*")
    stored_bytes = sum(
        sum(len(value) for value in option_snapshot.redis.zrange(key, 0, -1))
        for key in keys
        if option_snapshot.redis.type(key) == b"zset"
    )
    assert stored_bytes == 102_400
    for cursor in cursors:
        assert (
            option_snapshot.page(
                cursor, limit=1, selected=[], validate_tables=lambda _: None
            )["results"]
            == values[:1]
        )


def test_concurrent_identical_option_snapshots_share_one_complete_payload(
    option_snapshot, monkeypatch
):
    values = [str(index) for index in range(250)]
    publication = Barrier(2)
    original_eval = option_snapshot.redis.eval

    def publish_together(*args, **kwargs):
        publication.wait(timeout=5)
        return original_eval(*args, **kwargs)

    monkeypatch.setattr(option_snapshot.redis, "eval", publish_together)
    with ThreadPoolExecutor(max_workers=2) as pool:
        cursors = list(
            pool.map(lambda _: option_snapshot.create(lambda: values, []), range(2))
        )

    keys = list(option_snapshot.redis.scan_iter(match=f"{option_snapshot.prefix}:*"))
    assert sum(option_snapshot.redis.type(key) == b"zset" for key in keys) == 1
    for cursor in cursors:
        assert (
            option_snapshot.page(
                cursor, limit=250, selected=["249"], validate_tables=lambda _: None
            )["results"]
            == values
        )


def test_reused_payload_keeps_each_readers_original_expiry(option_snapshot):
    with freeze_time("2026-01-01 00:00:00") as clock:
        first = option_snapshot.create(lambda: ["Alpha", "Beta", "Gamma"], [])
        clock.move_to("2026-01-01 00:30:00")
        second = option_snapshot.create(lambda: ["Alpha", "Beta", "Gamma"], [])

        clock.move_to("2026-01-01 00:59:00")
        first_page = option_snapshot.page(
            first, limit=1, selected=[], validate_tables=lambda _: None
        )
        assert first_page["snapshot"] == first
        assert first_page["results"] == ["Alpha"]

        clock.move_to("2026-01-01 01:00:01")
        for cursor in (first, first_page["next"], first_page["snapshot"]):
            with pytest.raises(DashboardFilterOptionsExpired):
                option_snapshot.page(
                    cursor, limit=1, selected=[], validate_tables=lambda _: None
                )
        assert option_snapshot.page(
            second, limit=1, selected=[], validate_tables=lambda _: None
        )["results"] == ["Alpha"]


@pytest.mark.parametrize(
    "values, table_ids, expected",
    [
        (["Beta", "Alpha"], [17], ["Beta", "Alpha"]),
        (["Alpha", "Beta"], [18], ["Alpha", "Beta"]),
    ],
)
def test_option_reuse_preserves_order_and_table_dependencies(
    option_snapshot, values, table_ids, expected
):
    first = option_snapshot.create(lambda: ["Alpha", "Beta"], [17])
    second = option_snapshot.create(lambda: values, table_ids)
    dependencies = []
    assert option_snapshot.page(
        first, limit=50, selected=[], validate_tables=dependencies.append
    )["results"] == ["Alpha", "Beta"]
    assert (
        option_snapshot.page(
            second, limit=50, selected=[], validate_tables=dependencies.append
        )["results"]
        == expected
    )
    assert dependencies == [[17], table_ids]


@pytest.mark.parametrize("part", ["values", "metadata"])
def test_option_payload_eviction_expires_readers_and_refresh_recovers(
    option_snapshot, part
):
    cursor = option_snapshot.create(lambda: ["Alpha", "Beta"], [])
    for key in option_snapshot.redis.scan_iter(match=f"{option_snapshot.prefix}:*"):
        if key.endswith(b":metadata") == (part == "metadata"):
            option_snapshot.redis.delete(key)
    with pytest.raises(DashboardFilterOptionsExpired):
        option_snapshot.page(
            cursor, limit=1, selected=[], validate_tables=lambda _: None
        )

    refreshed = option_snapshot.create(lambda: ["Alpha", "Beta"], [])
    assert option_snapshot.page(
        refreshed, limit=50, selected=[], validate_tables=lambda _: None
    )["results"] == ["Alpha", "Beta"]


def test_evicted_staging_payload_is_not_published(option_snapshot):
    def values():
        yield from (str(index) for index in range(100))
        for key in option_snapshot.redis.scan_iter(match=f"{option_snapshot.prefix}:*"):
            option_snapshot.redis.delete(key)
        yield "last"

    with pytest.raises(DashboardFilterOptionsExpired):
        option_snapshot.create(values, [])
    assert (
        list(option_snapshot.redis.scan_iter(match=f"{option_snapshot.prefix}:*")) == []
    )


@pytest.mark.parametrize("cursor", [None, 42, "invalid"])
def test_malformed_option_cursors_expire(option_snapshot, cursor):
    with pytest.raises(DashboardFilterOptionsExpired):
        option_snapshot.page(
            cursor, limit=1, selected=[], validate_tables=lambda _: None
        )


@pytest.mark.parametrize(
    "payload",
    [None, [], ["a" * 64, 0], ["a" * 64, -1, 9999999999], ["a" * 64, 0, "future"]],
)
def test_malformed_signed_option_cursors_expire(option_snapshot, payload):
    cursor = signing.Signer(salt=option_snapshot.salt).sign_object(payload)
    with pytest.raises(DashboardFilterOptionsExpired):
        option_snapshot.page(
            cursor, limit=1, selected=[], validate_tables=lambda _: None
        )


def test_legacy_option_cursors_expire(option_snapshot):
    cursor = signing.dumps([uuid4().hex, 0], salt=option_snapshot.salt)
    with pytest.raises(DashboardFilterOptionsExpired):
        option_snapshot.page(
            cursor, limit=1, selected=[], validate_tables=lambda _: None
        )
