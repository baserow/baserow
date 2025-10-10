from unittest.mock import MagicMock, patch

from django.test.utils import override_settings

import pytest

from baserow.config.db_routers import (
    DEFAULT_DB_ALIAS,
    ReadReplicaRouter,
    clear_db_state,
    get_db_alias,
)


@pytest.mark.replica
@pytest.mark.django_db
@override_settings(DATABASE_READ_REPLICAS=["replica1", "replica2"])
def test_router_uses_replica_outside_transaction_and_sticks():
    router = ReadReplicaRouter()
    clear_db_state()

    mock_conn = MagicMock()
    mock_conn.get_autocommit.return_value = True
    mock_conn.in_atomic_block = False

    with patch("django.db.transaction.get_connection", return_value=mock_conn):
        # Outside transaction should use replica and stick to it
        alias1 = router.db_for_read(model=None)
        assert alias1 in ["replica1", "replica2"]
        assert get_db_alias() == alias1

        alias2 = router.db_for_read(model=None)
        assert alias2 == alias1


@pytest.mark.replica
@pytest.mark.django_db
@override_settings(DATABASE_READ_REPLICAS=["replica1", "replica2"])
def test_router_switches_to_default_inside_transaction():
    router = ReadReplicaRouter()
    clear_db_state()

    # Mock connection for outside transaction
    mock_conn_outside = MagicMock()
    mock_conn_outside.get_autocommit.return_value = True
    mock_conn_outside.in_atomic_block = False

    with patch("django.db.transaction.get_connection", return_value=mock_conn_outside):
        # Start outside transaction - should use replica
        alias_outside = router.db_for_read(model=None)
        assert alias_outside in ["replica1", "replica2"]

    # Mock connection for inside transaction
    mock_conn_inside = MagicMock()
    mock_conn_inside.get_autocommit.return_value = False
    mock_conn_inside.in_atomic_block = True

    with patch("django.db.transaction.get_connection", return_value=mock_conn_inside):
        # Enter transaction - should switch to default and stick
        alias1 = router.db_for_read(model=None)
        assert alias1 == DEFAULT_DB_ALIAS

        alias2 = router.db_for_read(model=None)
        assert alias2 == DEFAULT_DB_ALIAS

    # After transaction, should still be default (sticky)
    with patch("django.db.transaction.get_connection", return_value=mock_conn_outside):
        alias3 = router.db_for_read(model=None)
        assert alias3 == DEFAULT_DB_ALIAS


@pytest.mark.replica
@pytest.mark.django_db
@override_settings(DATABASE_READ_REPLICAS=["replica1", "replica2"])
def test_write_switches_to_default_and_sticks():
    router = ReadReplicaRouter()
    clear_db_state()

    # Mock connection for outside transaction
    mock_conn = MagicMock()
    mock_conn.get_autocommit.return_value = True
    mock_conn.in_atomic_block = False

    with patch("django.db.transaction.get_connection", return_value=mock_conn):
        # Start outside transaction - should use replica
        alias_before_write = router.db_for_read(model=None)
        assert alias_before_write in ["replica1", "replica2"]

        # Write should switch to default
        write_alias = router.db_for_write(model=None)
        assert write_alias == DEFAULT_DB_ALIAS

        # Read after write should still be default
        read_after_write = router.db_for_read(model=None)
        assert read_after_write == DEFAULT_DB_ALIAS
