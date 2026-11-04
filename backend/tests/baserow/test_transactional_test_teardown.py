from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.testcases import TransactionTestCase

import pytest

from baserow.core.models import Workspace


def teardown_transactional_test():
    """
    Runs the database teardown of a `transaction=True` test, which
    `tests/conftest.py` replaces. Calling it once first makes sure the next call
    can take the fast path, because the first teardown of a worker is a full flush.
    """

    TransactionTestCase()._fixture_teardown()


@pytest.mark.django_db(transaction=True)
def test_teardown_removes_rows_added_to_post_migrate_tables():
    teardown_transactional_test()
    ContentType.objects.create(app_label="tests", model="addedbyatest")

    teardown_transactional_test()

    assert not ContentType.objects.filter(app_label="tests").exists()


@pytest.mark.django_db(transaction=True)
def test_teardown_restores_rows_removed_from_post_migrate_tables():
    teardown_transactional_test()
    ContentType.objects.filter(app_label="auth", model="group").delete()
    ContentType.objects.clear_cache()

    teardown_transactional_test()

    assert ContentType.objects.get_for_model(Group)
    assert Permission.objects.filter(codename="add_group").exists()


@pytest.mark.django_db(transaction=True)
def test_teardown_leaves_emptied_tables_without_pages():
    # Like a TRUNCATE, so that the rows of the next test can't be written into the
    # space freed by this one and come back out of the order they were created in.
    teardown_transactional_test()
    Workspace.objects.bulk_create(Workspace(name=str(i)) for i in range(3000))
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM {Workspace._meta.db_table} WHERE id % 2 = 0")

    teardown_transactional_test()

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_relation_size(%s)", [Workspace._meta.db_table])
        assert cursor.fetchone()[0] == 0
