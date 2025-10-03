from unittest.mock import patch

import pytest

from baserow.config.db_routers import (
    ReadReplicaRouter,
    clear_db_state,
    get_read_alias,
    is_write_mode,
)
from baserow.config.utils import manage_db_state


@pytest.mark.replica
@pytest.mark.django_db
def test_router_picks_and_remembers_read_replica():
    router = ReadReplicaRouter()
    clear_db_state()

    with patch(
        "baserow.config.db_routers.DATABASE_READ_REPLICAS", ["replica1", "replica2"]
    ):
        alias1 = router.db_for_read(model=None)
        assert alias1 in ["replica1", "replica2"]
        assert get_read_alias() == alias1
        assert not is_write_mode()

        alias2 = router.db_for_read(model=None)
        assert alias2 == alias1


@pytest.mark.replica
@pytest.mark.django_db
def test_router_switches_to_write_and_sticks_after_first_write():
    router = ReadReplicaRouter()
    clear_db_state()

    with patch(
        "baserow.config.db_routers.DATABASE_READ_REPLICAS", ["replica1", "replica2"]
    ):
        alias = router.db_for_read(model=None)
        assert alias in ["replica1", "replica2"]
        assert not is_write_mode()

        write_alias = router.db_for_write(model=None)
        assert write_alias == "default"
        assert is_write_mode()

        read_after_write = router.db_for_read(model=None)
        assert read_after_write == "default"


@pytest.mark.replica
@pytest.mark.django_db
def test_manage_db_state_decorator_clears_state_before_and_after():
    router = ReadReplicaRouter()
    clear_db_state()

    with patch(
        "baserow.config.db_routers.DATABASE_READ_REPLICAS", ["replica1", "replica2"]
    ):

        @manage_db_state
        def do_reads_then_finish():
            assert get_read_alias() is None
            assert not is_write_mode()
            alias = router.db_for_read(model=None)
            assert alias in ["replica1", "replica2"]
            assert get_read_alias() == alias

        do_reads_then_finish()

        assert get_read_alias() is None
        assert not is_write_mode()


@pytest.mark.replica
@pytest.mark.django_db
def test_manage_db_state_decorator_write_first_pins_writer():
    router = ReadReplicaRouter()
    clear_db_state()

    with patch(
        "baserow.config.db_routers.DATABASE_READ_REPLICAS", ["replica1", "replica2"]
    ):

        @manage_db_state(write_first=True)
        def do_write_first_then_read():
            assert is_write_mode()
            alias = router.db_for_read(model=None)
            assert alias == "default"

        do_write_first_then_read()

        assert get_read_alias() is None
        assert not is_write_mode()
