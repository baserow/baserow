import asyncio
import contextlib
import os
import sys
import threading
from contextlib import ExitStack, contextmanager
from datetime import date, datetime
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional
from unittest.mock import patch

from django.conf import settings as django_settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS, OperationalError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext

import pytest
from asgiref.sync import async_to_sync
from faker import Faker
from loguru import logger
from pygments import highlight
from pygments.formatters import TerminalFormatter
from pygments.lexers import PostgresLexer
from pyinstrument import Profiler
from rest_framework.test import APIClient, APIRequestFactory
from sqlparse import format

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.fields import SerialField
from baserow.contrib.database.fields.models import LinkRowField
from baserow.contrib.database.webhooks.registries import webhook_event_type_registry
from baserow.core.cache import local_cache
from baserow.core.context import clear_current_workspace_id
from baserow.core.exceptions import PermissionDenied
from baserow.core.jobs.registries import job_type_registry
from baserow.core.permission_manager import CorePermissionManagerType
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.utils import ServiceAdhocRefinements
from baserow.core.trash.trash_types import WorkspaceTrashableItemType
from baserow.core.user_sources.registries import UserSourceCount
from baserow.core.utils import get_value_at_path
from baserow.test_utils.setup_formulas import iter_formula_pgsql_functions

SKIP_FLAGS = ["disabled-in-ci", "once-per-day-in-ci"]
COMMAND_LINE_FLAG_PREFIX = "--run-"

# List of heavy callables to defer by default during tests
# Used by defer_heavy_signals fixture
DEFAULT_DEFERRED_CALLABLES: List[str] = [
    "baserow.ws.tasks.broadcast_to_channel_group.delay",
    "baserow.ws.tasks.broadcast_to_users.delay",
    "baserow.ws.tasks.broadcast_to_permitted_users.delay",
    "baserow.ws.tasks.broadcast_to_group.delay",
    "baserow.ws.tasks.broadcast_to_groups.delay",
    "baserow.ws.tasks.broadcast_application_created.delay",
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
    "baserow.contrib.database.table.tasks.update_table_usage.delay",
    "baserow.core.notifications.tasks.send_queued_notifications_to_users.delay",
    "baserow.contrib.database.views.tasks.update_view_index.delay",
]


# Provides a new fake instance for each class. Solve uniqueness problem sometimes.
@pytest.fixture(scope="class", autouse=True)
def fake():
    yield Faker()


# We need to manually deal with the event loop since we are using asyncio in the
# tests in this directory and they have some issues when it comes to pytest.
# This solution is taken from: https://bit.ly/3UJ90co
@pytest.fixture(scope="session")
def async_event_loop():
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def data_fixture(fake):
    from .fixtures import Fixtures

    # Foreign keys are typically created as deferred constraints
    # that are checked only at the end of a transaction.
    # However, such checks cannot be postponed to the end of a transaction
    # if a table is manipulated in that transaction after rows with
    # foreign keys are inserted.
    # This is a workaround for our tests that make constraint checking
    # immediate and hence allows tests to create table, insert rows
    # with foreign keys and do ALTER TABLE on such table in the same
    # transaction.
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    return Fixtures(fake)


class StreamingAPIClient(APIClient):
    """Custom API client that properly handles streaming responses"""

    async def _consume_async_generator(self, async_gen: AsyncGenerator) -> List:
        """Helper to consume async generator"""
        chunks = []
        async for chunk in async_gen:
            chunks.append(chunk)
        return chunks

    def request(self, **kwargs):
        response = super().request(**kwargs)

        # If it's a streaming response, don't consume it yet, but store the original
        # streaming_content so we can consume it later if needed.
        if hasattr(response, "streaming_content"):
            response._streaming_content = response.streaming_content

            def stream_chunks() -> list[str]:
                content = response._streaming_content

                if hasattr(content, "__aiter__"):
                    return async_to_sync(self._consume_async_generator)(content)
                else:
                    return list(content)

            response.stream_chunks = stream_chunks

        return response


@pytest.fixture()
def api_client():
    return StreamingAPIClient()


@pytest.fixture
def api_request_factory():
    """
    Returns an instance of the DRF APIRequestFactory.
    """

    return APIRequestFactory()


@pytest.fixture(autouse=True)
def clear_cache():
    """Automatically clear all caches before each test."""

    # fakeredis cache
    cache.clear()

    # Workspace search table cache
    from baserow.contrib.database.search.handler import (
        _generate_search_table_model,
        _workspace_search_table_exists,
    )

    _generate_search_table_model.cache_clear()
    _workspace_search_table_exists.cache_clear()

    # Thread-local cache
    with local_cache.context():
        yield


@pytest.fixture(autouse=True)
def defer_heavy_signals(request):
    """
    Defer heavy callables by default to speed up tests.

    Opt-out options:
        @pytest.mark.enable_all_signals - Enable all deferred signals
        @pytest.mark.enable_signals("path.to.callable") - Enable specific signal(s)
    """

    if request.node.get_closest_marker("enable_all_signals"):
        yield
        return

    signals_to_defer = set(DEFAULT_DEFERRED_CALLABLES)

    enable_signals_marker = request.node.get_closest_marker("enable_signals")
    if enable_signals_marker:
        signals_to_enable = set()
        if enable_signals_marker.args:
            signals_to_enable.update(enable_signals_marker.args)
        if enable_signals_marker.kwargs.get("signals"):
            signals_to_enable.update(enable_signals_marker.kwargs["signals"])
        signals_to_defer -= signals_to_enable

    if not signals_to_defer:
        yield
        return

    with ExitStack() as stack:
        for name in signals_to_defer:
            stack.enter_context(patch(name, lambda *args, **kwargs: None))
        yield


@pytest.fixture
def reset_schema(django_db_blocker):
    yield
    with django_db_blocker.unblock():
        call_command("migrate", verbosity=0, database=DEFAULT_DB_ALIAS)


@pytest.fixture()
def environ():
    original_env = os.environ.copy()
    yield os.environ
    for key, value in original_env.items():
        os.environ[key] = value


@pytest.fixture()
def print_sql():
    with CaptureQueriesContext(connection) as ctx:
        yield
        for query in ctx.captured_queries:
            formatted_query = format(query.get("sql", ""), reindent=True)
            print()
            print(highlight(formatted_query, PostgresLexer(), TerminalFormatter()))


@pytest.fixture()
def mutable_field_type_registry():
    from baserow.contrib.database.fields.registries import field_type_registry

    before = field_type_registry.registry.copy()
    field_type_registry.get_for_class.cache_clear()
    yield field_type_registry
    field_type_registry.get_for_class.cache_clear()
    field_type_registry.registry = before


@pytest.fixture()
def mutable_action_registry():
    from baserow.core.action.registries import action_type_registry

    before = action_type_registry.registry.copy()
    yield action_type_registry
    action_type_registry.registry = before


@pytest.fixture
def mutable_application_registry():
    from baserow.core.registries import application_type_registry

    before = application_type_registry.registry.copy()
    application_type_registry.get_for_class.cache_clear()
    yield application_type_registry
    application_type_registry.get_for_class.cache_clear()
    application_type_registry.registry = before


@pytest.fixture
def mutable_trash_item_type_registry():
    from baserow.core.trash.registries import trash_item_type_registry

    before = trash_item_type_registry.registry.copy()
    trash_item_type_registry.get_for_class.cache_clear()
    yield trash_item_type_registry
    trash_item_type_registry.get_for_class.cache_clear()
    trash_item_type_registry.registry = before


@pytest.fixture
def mutable_permission_manager_registry():
    from baserow.core.registries import permission_manager_type_registry

    before = permission_manager_type_registry.registry.copy()
    yield permission_manager_type_registry
    permission_manager_type_registry.registry = before


@pytest.fixture
def mutable_notification_type_registry():
    from baserow.core.notifications.registries import notification_type_registry

    before = notification_type_registry.registry.copy()
    yield notification_type_registry
    notification_type_registry.registry = before


@pytest.fixture()
def mutable_builder_data_provider_registry():
    from baserow.contrib.builder.data_providers.registries import (
        builder_data_provider_type_registry,
    )

    before = builder_data_provider_type_registry.registry.copy()
    yield builder_data_provider_type_registry
    builder_data_provider_type_registry.registry = before


@pytest.fixture()
def mutable_user_source_registry():
    from baserow.core.user_sources.registries import user_source_type_registry

    before = user_source_type_registry.registry.copy()
    user_source_type_registry.get_for_class.cache_clear()
    yield user_source_type_registry
    user_source_type_registry.get_for_class.cache_clear()
    user_source_type_registry.registry = before


@pytest.fixture()
def mutable_trash_operation_type_registry():
    from baserow.core.trash.registries import trash_operation_type_registry

    before = trash_operation_type_registry.registry.copy()
    trash_operation_type_registry.get_for_class.cache_clear()
    yield trash_operation_type_registry
    trash_operation_type_registry.get_for_class.cache_clear()
    trash_operation_type_registry.registry = before


@pytest.fixture()
def mutable_builder_workflow_action_registry():
    from baserow.contrib.builder.workflow_actions.registries import (
        builder_workflow_action_type_registry,
    )

    before = builder_workflow_action_type_registry.registry.copy()
    builder_workflow_action_type_registry.get_for_class.cache_clear()
    yield builder_workflow_action_type_registry
    builder_workflow_action_type_registry.get_for_class.cache_clear()
    builder_workflow_action_type_registry.registry = before


@pytest.fixture()
def mutable_job_type_registry():
    with patch.object(job_type_registry, "registry", {}):
        job_type_registry.get_for_class.cache_clear()
        yield job_type_registry
        job_type_registry.get_for_class.cache_clear()


@pytest.fixture()
def mutable_webhook_event_type_registry():
    with patch.object(webhook_event_type_registry, "registry", {}):
        webhook_event_type_registry.get_for_class.cache_clear()
        yield webhook_event_type_registry
        webhook_event_type_registry.get_for_class.cache_clear()


@pytest.fixture()
def mutable_element_type_registry():
    from baserow.contrib.builder.elements.registries import element_type_registry

    before = element_type_registry.registry.copy()
    yield element_type_registry
    element_type_registry.registry = before


@pytest.fixture()
def stub_trash_operation_type(data_fixture, mutable_trash_operation_type_registry):
    @contextlib.contextmanager
    def stubbed(
        type_managed=False,
        type_send_deleted_signal=True,
        type_send_created_signal=True,
    ):
        from baserow.core.trash.registries import (
            TrashOperationType,
            trash_operation_type_registry,
        )

        class StubbedTrashOperationType(TrashOperationType):
            type = "stubbed"
            managed = type_managed
            send_post_trash_deleted_signal = type_send_deleted_signal
            send_post_restore_created_signal = type_send_created_signal

        operation_type = StubbedTrashOperationType()
        mutable_trash_operation_type_registry.registry[
            StubbedTrashOperationType.type
        ] = StubbedTrashOperationType()
        trash_operation_type_registry.get_for_class.cache_clear()

        yield operation_type

    return stubbed


@pytest.fixture()
def stub_user_source_registry(data_fixture, mutable_user_source_registry, fake):
    from baserow.core.user_sources.registries import UserSourceType

    @contextlib.contextmanager
    def stubbed_user_source_registry_first_type(
        authenticate_return=None,
        get_user_return=None,
        list_users_return=None,
        gen_uid_return=None,
        get_user_count_return=None,
        update_user_count_return=None,
        properties_requiring_user_recount_return=None,
    ):
        """
        Replace first user_source type with the stub class
        """

        from baserow.core.user_sources.registries import user_source_type_registry

        user_source_type = list(mutable_user_source_registry.get_all())[0]

        class StubbedUserSourceType(UserSourceType):
            type = user_source_type.type
            model_class = user_source_type.model_class
            properties_requiring_user_recount = properties_requiring_user_recount_return

            def get_user_count(self, user_source, force_recount=False):
                if get_user_count_return:
                    if callable(get_user_count_return):
                        return get_user_count_return(user_source, force_recount)
                    return UserSourceCount(count=5, last_updated=datetime.now())

            def update_user_count(self, user_source=None):
                if update_user_count_return:
                    if callable(update_user_count_return):
                        return update_user_count_return(user_source)
                    return None

            def gen_uid(self, user_source):
                if gen_uid_return:
                    if callable(gen_uid_return):
                        return gen_uid_return(user_source)
                    return gen_uid_return

                return str(fake.uuid4())

            def list_users(self, user_source, count: int = 5, search: str = ""):
                if list_users_return:
                    if callable(list_users_return):
                        return list_users_return(user_source, count, search)
                    return list_users_return

                return [data_fixture.create_user_source_user(user_source=user_source)]

            def get_user(self, user_source, **kwargs):
                if get_user_return:
                    if callable(get_user_return):
                        return get_user_return(user_source, **kwargs)
                    return get_user_return
                return data_fixture.create_user_source_user(user_source=user_source)

            def create_user(self, user_source, email, name):
                return data_fixture.create_user_source_user(user_source=user_source)

            def authenticate(self, user_source, **kwargs):
                if authenticate_return:
                    if callable(authenticate_return):
                        return authenticate_return(user_source, **kwargs)
                    return authenticate_return
                return data_fixture.create_user_source_user(user_source=user_source)

            def get_roles(self):
                return []

        mutable_user_source_registry.registry[
            user_source_type.type
        ] = StubbedUserSourceType()
        user_source_type_registry.get_for_class.cache_clear()

        yield user_source_type_registry

    return stubbed_user_source_registry_first_type


@pytest.fixture()
def patch_filefield_storage(tmpdir):
    """
    Patches all filefield storages from all models with the one given in parameter
    or a newly created one.
    """

    from django.apps import apps
    from django.core.files.storage import FileSystemStorage
    from django.db.models import FileField

    # Cache the storage
    _storage = None

    @contextlib.contextmanager
    def patch(new_storage=None):
        nonlocal _storage
        if new_storage is None:
            if not _storage:
                # Create a default storage if none given
                _storage = FileSystemStorage(
                    location=str(tmpdir), base_url="http://localhost"
                )
            new_storage = _storage

        previous_storages = {}
        # Replace storage
        for model in apps.get_models():
            filefields = (f for f in model._meta.fields if isinstance(f, FileField))
            for filefield in filefields:
                previous_storages[
                    f"{model._meta.label}_{filefield.name}"
                ] = filefield.storage
                filefield.storage = new_storage

        yield new_storage

        # Restore previous storage
        for model in apps.get_models():
            filefields = (f for f in model._meta.fields if isinstance(f, FileField))

            for filefield in filefields:
                filefield.storage = previous_storages[
                    f"{model._meta.label}_{filefield.name}"
                ]

    return patch


# We reuse this file in the premium/enterprise backend folder, if you run a pytest
# session over plugins and the core at the same time pytest will crash if this
# called multiple times.
def pytest_addoption(parser):
    # Unfortunately a simple decorator doesn't work here as pytest is doing some
    # exciting reflection of sorts over this function and crashes if it is wrapped.
    if not hasattr(pytest_addoption, "already_run"):
        for flag in SKIP_FLAGS:
            parser.addoption(
                f"{COMMAND_LINE_FLAG_PREFIX}{flag}",
                action="store_true",
                default=False,
                help=f"run {flag} tests",
            )
        pytest_addoption.already_run = True


def pytest_configure(config):
    if not hasattr(pytest_configure, "already_run"):
        for flag in SKIP_FLAGS:
            config.addinivalue_line(
                "markers",
                f"{flag}: mark test so it only runs when the "
                f"{COMMAND_LINE_FLAG_PREFIX}{flag} flag is provided to pytest",
            )
        config.addinivalue_line(
            "markers",
            "enable_all_signals: Disables signal deferral for this test",
        )
        config.addinivalue_line(
            "markers",
            "enable_signals(callable_paths): Enables specific signals for this test",
        )
        pytest_configure.already_run = True


def pytest_collection_modifyitems(config, items):
    enabled_flags = {
        flag
        for flag in SKIP_FLAGS
        if config.getoption(f"{COMMAND_LINE_FLAG_PREFIX}{flag}")
    }
    for item in items:
        for flag in SKIP_FLAGS:
            flag_for_python = flag.replace("-", "_")
            if flag_for_python in item.keywords and flag not in enabled_flags:
                skip_marker = pytest.mark.skip(
                    reason=f"need {COMMAND_LINE_FLAG_PREFIX}{flag} option to run"
                )
                item.add_marker(skip_marker)
                break


@pytest.fixture()
def profiler():
    """
    A fixture to provide an easy way to profile code in your tests.
    """

    TESTS_ROOT = Path.cwd()
    PROFILE_ROOT = TESTS_ROOT / ".profiles"
    profiler = Profiler()

    @contextlib.contextmanager
    def profile_this(
        print_result: bool = True,
        html_report_name: str = "",
        output_text_params: Optional[Dict] = None,
        output_html_params: Optional[Dict] = None,
    ):
        """
        Context manager to profile something.
        """

        profiler.start()

        yield profiler

        profiler.stop()

        output_text_params = output_text_params or {}
        output_html_params = output_html_params or {}

        output_text_params.setdefault("unicode", True)
        output_text_params.setdefault("color", True)

        if print_result:
            print(profiler.output_text(**output_text_params))

        if html_report_name:
            PROFILE_ROOT.mkdir(exist_ok=True)
            results_file = PROFILE_ROOT / f"{html_report_name}.html"
            with open(results_file, "w", encoding="utf-8") as f_html:
                f_html.write(profiler.output_html(**output_html_params))

        profiler.reset()

    return profile_this


class BaseMaxLocksPerTransactionStub:
    # Determines whether we raise an `OperationalError` about
    # `max_locks_per_transaction` or something else.
    raise_transaction_exception: bool = True

    def get_message(self) -> str:
        message = "An operational error has occurred."
        if self.raise_transaction_exception:
            message = "HINT:  You might need to increase max_locks_per_transaction."
        return message


class MaxLocksPerTransactionExceededApplicationType(
    DatabaseApplicationType, BaseMaxLocksPerTransactionStub
):
    def export_serialized(self, *args, **kwargs):
        raise OperationalError(self.get_message())


class MaxLocksPerTransactionExceededGroupTrashableItemType(
    WorkspaceTrashableItemType, BaseMaxLocksPerTransactionStub
):
    def permanently_delete_item(self, *args, **kwargs):
        raise OperationalError(self.get_message())


@pytest.fixture
def application_type_serialized_raising_operationalerror(
    mutable_application_registry,
) -> callable:
    """
    Overrides the existing `DatabaseApplicationType` with a test only stub version that
    optionally (if `raise_transaction_exception` is `True`) raises an `OperationalError`
    about `max_locks_per_transaction` being exceeded when `export_serialized` is called.
    """

    @contextlib.contextmanager
    def _perform_stub(raise_transaction_exception: bool = True):
        stub_application_type = MaxLocksPerTransactionExceededApplicationType()
        stub_application_type.raise_transaction_exception = raise_transaction_exception
        mutable_application_registry.get_for_class.cache_clear()
        mutable_application_registry.registry[
            DatabaseApplicationType.type
        ] = stub_application_type

        yield stub_application_type

    return _perform_stub


@pytest.fixture
def trash_item_type_perm_delete_item_raising_operationalerror(
    mutable_trash_item_type_registry,
) -> callable:
    """
    Overrides the existing `GroupTrashableItemType` with a test only stub version that
    optionally (if `raise_transaction_exception` is `True`) raises an `OperationalError`
    about `max_locks_per_transaction` being exceeded when `permanently_delete_item`
    is called.
    """

    @contextlib.contextmanager
    def _perform_stub(raise_transaction_exception: bool = True):
        stub_trash_item_type = MaxLocksPerTransactionExceededGroupTrashableItemType()
        stub_trash_item_type.raise_transaction_exception = raise_transaction_exception
        mutable_trash_item_type_registry.get_for_class.cache_clear()
        mutable_trash_item_type_registry.registry[
            WorkspaceTrashableItemType.type
        ] = stub_trash_item_type

        yield stub_trash_item_type

    return _perform_stub


class StubbedCorePermissionManagerType(CorePermissionManagerType):
    """
    Stub for the first permission manager.
    """

    def __init__(self, raise_permission_denied: bool = False):
        self.raise_permission_denied = raise_permission_denied

    def check_multiple_permissions(self, checks, workspace=None, include_trash=False):
        result = {}
        for check in checks:
            if self.raise_permission_denied:
                result[check] = PermissionDenied()
            else:
                result[check] = True

        return result


@pytest.fixture
def bypass_check_permissions(
    mutable_permission_manager_registry,
) -> CorePermissionManagerType:
    """
    Overrides the existing `CorePermissionManagerType` so that
    we can always `return True` on a `check_permissions` call.
    """

    stub_core_permission_manager = StubbedCorePermissionManagerType()

    for perm_manager in django_settings.PERMISSION_MANAGERS:
        mutable_permission_manager_registry.registry[
            perm_manager
        ] = stub_core_permission_manager

    yield stub_core_permission_manager


@pytest.fixture
def stub_check_permissions() -> callable:
    """
    Overrides the existing `CorePermissionManagerType` so that
    we can return True or raise a PermissionDenied exception on a `check_permissions`
    call.
    """

    @contextlib.contextmanager
    def _perform_stub(
        raise_permission_denied: bool = False,
    ) -> CorePermissionManagerType:
        from baserow.core.registries import permission_manager_type_registry

        before = permission_manager_type_registry.registry.copy()
        stub_core_permission_manager = StubbedCorePermissionManagerType(
            raise_permission_denied
        )
        first_manager = django_settings.PERMISSION_MANAGERS[0]
        permission_manager_type_registry.registry[
            first_manager
        ] = stub_core_permission_manager
        yield stub_core_permission_manager
        permission_manager_type_registry.registry = before

    return _perform_stub


@pytest.fixture
def teardown_table_metadata():
    """
    If you are creating `database_table` metadata rows in your tests without actually
    making the real user tables, this fixture will automatically clean them up for you
    so later tests won't crash due to the weird metadata state.
    """

    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("truncate table database_table cascade;")


class TestMigrator:
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(target)
        new_state = executor.loader.project_state(target)
        return new_state


def _set_suffix_to_test_databases(suffix: str) -> None:
    from django.conf import settings

    for db_settings in settings.DATABASES.values():
        test_name = db_settings.get("TEST", {}).get("NAME")

        if not test_name:
            test_name = "test_{}".format(db_settings["NAME"])

        if test_name == ":memory:":
            continue

        db_settings.setdefault("TEST", {})
        db_settings["TEST"]["NAME"] = "{}_{}".format(test_name, suffix)


def _remove_suffix_from_test_databases(suffix: str) -> None:
    from django.conf import settings

    for db_settings in settings.DATABASES.values():
        db_settings["TEST"]["NAME"] = db_settings["TEST"]["NAME"].replace(suffix, "")


@pytest.fixture(scope="session")
def second_separate_database_for_migrations(
    request,
    django_test_environment: None,
    django_db_blocker,
) -> None:
    from django.test.utils import setup_databases

    setup_databases_args = {}

    # Ensure this second database never clashes with the normal test databases
    # by adding another suffix...
    suffix = f"second_db_{os.getpid()}"
    _set_suffix_to_test_databases(suffix)

    with django_db_blocker.unblock():
        db_cfg = setup_databases(
            verbosity=request.config.option.verbose,
            interactive=False,
            **setup_databases_args,
        )

        def teardown_database() -> None:
            with django_db_blocker.unblock():
                try:
                    for c, old_name, destroy in db_cfg:
                        c.creation.destroy_test_db(
                            old_name,
                            request.config.option.verbose,
                            False,
                            suffix=suffix,
                        )
                except Exception as exc:
                    request.node.warn(
                        pytest.PytestWarning(
                            f"Error when trying to teardown test databases: {exc!r}"
                        )
                    )
                finally:
                    _remove_suffix_from_test_databases(suffix)

        request.addfinalizer(teardown_database)
        yield

        for _, name, _ in db_cfg:
            print(f"Created migration database {name}")


@pytest.fixture
def migrator(second_separate_database_for_migrations, reset_schema):
    yield TestMigrator()


@pytest.fixture
def disable_full_text_search(settings):
    settings.PG_FULLTEXT_SEARCH_ENABLED = False


@pytest.fixture(autouse=True)
def mutable_generative_ai_model_type_registry():
    from baserow.core.generative_ai.registries import generative_ai_model_type_registry

    before = generative_ai_model_type_registry.registry.copy()
    yield generative_ai_model_type_registry
    generative_ai_model_type_registry.registry = before


@pytest.fixture(autouse=True)
def run_clear_current_workspace_id_after_test():
    """Clear workspace_id stored in local context after each test."""

    yield
    clear_current_workspace_id()


def fake_import_formula(formula, id_mapping):
    return formula


class FakeDispatchContext(DispatchContext):
    own_properties = [
        "context",
        "_public_allowed_properties",
        "_searchable_fields",
        "_search_query",
        "_count",
    ]

    def __init__(self, **kwargs):
        super().__init__()
        self.context = kwargs.pop("context", {})
        self._public_allowed_properties = kwargs.pop("public_allowed_properties", None)
        self._searchable_fields = kwargs.pop("searchable_fields", [])
        self._search_query = kwargs.pop("search_query", None)
        self._count = kwargs.pop("count", 100)

        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def is_publicly_searchable(self):
        return True

    def search_query(self):
        return self._search_query

    def searchable_fields(self):
        return self._searchable_fields

    @property
    def is_publicly_filterable(self):
        return True

    def filters(self):
        return None

    @property
    def is_publicly_sortable(self):
        return True

    def sortings(self):
        return None

    def range(self, service):
        return [0, self._count]

    def __getitem__(self, key: str) -> Any:
        if key == "test":
            return 2
        if key == "test1":
            return 1
        if key == "test2":
            return ""
        if key == "test999":
            return "999"

        return get_value_at_path(self.context, key)

    @property
    def public_allowed_properties(self) -> Optional[Dict[str, Dict[int, List[str]]]]:
        return self._public_allowed_properties

    def validate_filter_search_sort_fields(
        self, fields: List[str], refinement: ServiceAdhocRefinements
    ):
        pass


@pytest.fixture()
def test_thread():
    """
    Run a side thread with an arbitrary function.

    This fixture allows to run a helper thread with an arbitrary function
    to test concurrent flows, i.e. in-Celery-task state changes.

    This fixture will increase min thread switching granularity for the test to
    to 0.00001s.

    It's advised to use threading primitives to communicate with the helper thread.

    A callable will be wrapped to log any error ocurred during the execution.

    A Thread object yielded from this fixture has .thread_stopped Event attached to
    simplify synchronization with the test code. This event is set when a
    callable finished it's work.

    >>> def test_x(test_thread):
        evt_start = threading.Event()
        evt_end = threading.Event()
        evt_can_end = threading.Event()

        def callable(*args, **kwargs):
            evt_start.set()
            assert evt_can_end(timeout=0.01)
            evt_end.set()

        with test_thread(callable, foo='bar') as t:
             # pick a moment to start
             t.start()
             evt_can_end.set()

             # wait for the callable to finish
             assert t.thread_stopped.wait(0.1)

        assert evt_start.is_set()
        assert evt_end.is_set()

    :return:
    """

    thread_stopped = threading.Event()

    def wrapper(c, *args, **kwargs):
        try:
            logger.info(f"running callable {c} with args {args} {kwargs}")
            return c(*args, **kwargs)
        except Exception as err:
            logger.error(f"error when running {c}: {err}", exc_info=True)
            raise
        finally:
            thread_stopped.set()

    @contextmanager
    def run_callable(callable, *args, **kwargs):
        t = threading.Thread(target=partial(wrapper, callable, *args, **kwargs))
        t.thread_stopped = thread_stopped
        switch_interval = 0.00001
        orig_switch_interval = sys.getswitchinterval()
        try:
            sys.setswitchinterval(switch_interval)
            yield t
        finally:
            while t.is_alive():
                t.join(0.01)
            sys.setswitchinterval(orig_switch_interval)

    yield run_callable


@pytest.fixture(scope="session", autouse=True)
def baserow_db_setup(django_db_setup, django_db_blocker):
    """
    Initialize the Baserow database for tests by installing custom pgSQL functions
    and sequences. Disable this fixture with BASEROW_TESTS_SETUP_DB_FIXTURE=off if
    running a subset of tests with `--no-migrations --reuse-db` and the pgSQL
    functions are not needed or if you want to run all migrations.
    """

    if getattr(django_settings, "BASEROW_TESTS_SETUP_DB_FIXTURE", False) is False:
        return

    def init_link_row_sequence():
        db_table = LinkRowField._meta.db_table
        db_column = "link_row_relation_id"

        sequence_name = SerialField.get_sequence_name(db_table, db_column)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SEQUENCE IF NOT EXISTS {sequence_name};")

    all_formula_functions = "\n".join(iter_formula_pgsql_functions())
    with django_db_blocker.unblock():
        with connection.cursor() as cursor:
            cursor.execute(all_formula_functions)

        init_link_row_sequence()


@pytest.fixture()
def use_tmp_media_root(tmpdir, settings):
    settings.MEDIA_ROOT = tmpdir


@pytest.fixture
def create_postgresql_test_table():
    table_name = "test_table"

    column_definitions = {
        "text_col": "TEXT",
        "char_col": "CHAR(10)",
        "int_col": "INTEGER",
        "float_col": "REAL",
        "numeric_col": "NUMERIC",
        "numeric2_col": "NUMERIC(100, 4)",
        "smallint_col": "SMALLINT",
        "bigint_col": "BIGINT",
        "decimal_col": "DECIMAL",
        "date_col": "DATE",
        "datetime_col": "TIMESTAMP",
        "boolean_col": "BOOLEAN",
    }

    # Create the schema of the initial table.
    create_table_sql = f"""
    CREATE TABLE {table_name} (
        id SERIAL PRIMARY KEY,
        {', '.join([f"{col_name} {col_type}" for col_name, col_type in column_definitions.items()])}
    )
    """

    # Inserts a couple of random rows for testing purposes.
    insert_sql = f"""
    INSERT INTO {table_name} ({', '.join(column_definitions.keys())})
    VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(create_table_sql)

            cursor.execute(
                insert_sql,
                (
                    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Maecenas non nunc et sapien ultricies blandit. ",
                    "Short char",
                    10,
                    10.10,
                    100,
                    "10.4444",
                    200,
                    99999999,
                    Decimal("99999999.22"),
                    date(2023, 1, 17),
                    datetime(2022, 2, 28, 12, 00),
                    True,
                ),
            )
            cursor.execute(
                insert_sql,
                (
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                ),
            )

        transaction.commit()

        yield table_name  # Provide table name to tests that need to access it

    finally:
        # Drop the table after test completes or fails
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
        transaction.commit()
