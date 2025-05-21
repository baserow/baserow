from collections import defaultdict
from decimal import Decimal

from django.db.models import QuerySet

import pytest
from freezegun.api import freeze_time

from baserow.core.exceptions import (
    ApplicationOperationNotSupported,
    CannotCalculateIntermediateOrder,
)
from baserow.core.user_sources.exceptions import UserSourceDoesNotExist
from baserow.core.user_sources.handler import UserSourceHandler
from baserow.core.user_sources.models import UserSource
from baserow.core.user_sources.registries import (
    DEFAULT_USER_ROLE_PREFIX,
    UserSourceType,
    user_source_type_registry,
)
from baserow.core.utils import MirrorDict
from baserow.test_utils.helpers import AnyStr


def pytest_generate_tests(metafunc):
    if "user_source_type" in metafunc.fixturenames:
        metafunc.parametrize(
            "user_source_type",
            [pytest.param(e, id=e.type) for e in user_source_type_registry.get_all()],
        )


@pytest.mark.django_db
def test_create_user_source(data_fixture, user_source_type: UserSourceType):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    user_source = UserSourceHandler().create_user_source(
        user_source_type,
        application=application,
        **user_source_type.prepare_values({}, user),
    )

    assert user_source.application.id == application.id

    assert user_source.order == 1
    assert UserSource.objects.count() == 1


@pytest.mark.django_db
def test_create_user_source_check_uid(data_fixture, stub_user_source_registry):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)

    def gen_uid(user_source):
        return f"{user_source.id}_test"

    with stub_user_source_registry(gen_uid_return=gen_uid):
        first_type = list(user_source_type_registry.get_all())[0]
        user_source = UserSourceHandler().create_user_source(
            first_type, application=application, **first_type.prepare_values({}, user)
        )

    assert user_source.uid == f"{user_source.id}_test"


@pytest.mark.django_db
def test_create_user_source_bad_application(data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_database_application(user=user)

    user_source_type = user_source_type_registry.get("local_baserow")

    with pytest.raises(ApplicationOperationNotSupported):
        UserSourceHandler().create_user_source(
            user_source_type,
            application=application,
            **user_source_type.prepare_values({}, user),
        )


@pytest.mark.django_db
def test_get_user_source(data_fixture):
    user_source = data_fixture.create_user_source_with_first_type()
    assert UserSourceHandler().get_user_source(user_source.id).id == user_source.id


@pytest.mark.django_db
def test_get_user_source_does_not_exist(data_fixture):
    with pytest.raises(UserSourceDoesNotExist):
        assert UserSourceHandler().get_user_source(0)


@pytest.mark.django_db
def test_get_user_sources(data_fixture):
    builder = data_fixture.create_builder_application()
    user_source1 = data_fixture.create_user_source_with_first_type(application=builder)
    user_source2 = data_fixture.create_user_source_with_first_type(application=builder)
    user_source3 = data_fixture.create_user_source_with_first_type(application=builder)

    user_sources = UserSourceHandler().get_user_sources(application=builder)

    assert [e.id for e in user_sources] == [
        user_source1.id,
        user_source2.id,
        user_source3.id,
    ]

    first_user_source_type = list(user_source_type_registry.get_all())[0]

    assert isinstance(user_sources[0], first_user_source_type.model_class)


@pytest.mark.django_db
def test_delete_user_source(data_fixture):
    user_source = data_fixture.create_user_source_with_first_type()

    UserSourceHandler().delete_user_source(user_source)

    assert UserSource.objects.count() == 0


@pytest.mark.django_db
def test_update_user_source(data_fixture, stub_user_source_registry):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)
    integration2 = data_fixture.create_local_baserow_integration(user=user)

    user_source = data_fixture.create_user_source_with_first_type(
        user=user, integration=integration
    )

    def gen_uid(user_source):
        return f"{user_source.id}_test"

    with stub_user_source_registry(gen_uid_return=gen_uid):
        user_source_type = user_source_type_registry.get("local_baserow")

        user_source_updated = UserSourceHandler().update_user_source(
            user_source_type, user_source, integration=integration2
        )

    assert user_source_updated.integration.id == integration2.id
    assert user_source.uid == f"{user_source.id}_test"


@pytest.mark.django_db
def test_update_user_source_invalid_values(data_fixture):
    user_source = data_fixture.create_user_source_with_first_type()

    user_source_type = user_source_type_registry.get("local_baserow")

    user_source_updated = UserSourceHandler().update_user_source(
        user_source_type, user_source, nonsense="hello"
    )

    assert not hasattr(user_source_updated, "nonsense")


@pytest.mark.django_db
def test_move_user_source_end_of_application(data_fixture):
    builder = data_fixture.create_builder_application()
    user_source1 = data_fixture.create_user_source_with_first_type(application=builder)
    user_source2 = data_fixture.create_user_source_with_first_type(application=builder)
    user_source3 = data_fixture.create_user_source_with_first_type(application=builder)

    user_source_moved = UserSourceHandler().move_user_source(user_source1)

    assert (
        UserSource.objects.filter(application=builder).last().id == user_source_moved.id
    )


@pytest.mark.django_db
def test_move_user_source_before(data_fixture):
    builder = data_fixture.create_builder_application()
    user_source1 = data_fixture.create_user_source_with_first_type(application=builder)
    user_source2 = data_fixture.create_user_source_with_first_type(application=builder)
    user_source3 = data_fixture.create_user_source_with_first_type(application=builder)

    UserSourceHandler().move_user_source(user_source3, before=user_source2)

    assert [e.id for e in UserSource.objects.filter(application=builder).all()] == [
        user_source1.id,
        user_source3.id,
        user_source2.id,
    ]


@pytest.mark.django_db
def test_move_user_source_before_fails(data_fixture):
    builder = data_fixture.create_builder_application()
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=builder, order="2.99999999999999999998"
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=builder, order="2.99999999999999999999"
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=builder, order="3.0000"
    )

    with pytest.raises(CannotCalculateIntermediateOrder):
        UserSourceHandler().move_user_source(user_source3, before=user_source2)


@pytest.mark.django_db
def test_recalculate_full_orders(data_fixture):
    builder = data_fixture.create_builder_application()
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=builder, order="1.99999999999999999999"
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=builder, order="2.00000000000000000000"
    )
    user_source3 = data_fixture.create_user_source_with_first_type(
        application=builder, order="1.99999999999999999999"
    )
    user_source4 = data_fixture.create_user_source_with_first_type(
        application=builder, order="2.10000000000000000000"
    )
    user_source5 = data_fixture.create_user_source_with_first_type(
        application=builder, order="3.00000000000000000000"
    )
    user_source6 = data_fixture.create_user_source_with_first_type(
        application=builder, order="1.00000000000000000001"
    )
    user_source7 = data_fixture.create_user_source_with_first_type(
        application=builder, order="3.99999999999999999999"
    )
    user_source8 = data_fixture.create_user_source_with_first_type(
        application=builder, order="4.00000000000000000001"
    )

    builder2 = data_fixture.create_builder_application()

    user_sourceA = data_fixture.create_user_source_with_first_type(
        application=builder2, order="1.99999999999999999999"
    )
    user_sourceB = data_fixture.create_user_source_with_first_type(
        application=builder2, order="2.00300000000000000000"
    )

    UserSourceHandler().recalculate_full_orders(builder)

    user_sources = UserSource.objects.filter(application=builder)
    assert user_sources[0].id == user_source6.id
    assert user_sources[0].order == Decimal("1.00000000000000000000")

    assert user_sources[1].id == user_source1.id
    assert user_sources[1].order == Decimal("2.00000000000000000000")

    assert user_sources[2].id == user_source3.id
    assert user_sources[2].order == Decimal("3.00000000000000000000")

    assert user_sources[3].id == user_source2.id
    assert user_sources[3].order == Decimal("4.00000000000000000000")

    assert user_sources[4].id == user_source4.id
    assert user_sources[4].order == Decimal("5.00000000000000000000")

    assert user_sources[5].id == user_source5.id
    assert user_sources[5].order == Decimal("6.00000000000000000000")

    assert user_sources[6].id == user_source7.id
    assert user_sources[6].order == Decimal("7.00000000000000000000")

    assert user_sources[7].id == user_source8.id
    assert user_sources[7].order == Decimal("8.00000000000000000000")

    # Other page user_sources shouldn't be reordered
    user_sources = UserSource.objects.filter(application=builder2)
    assert user_sources[0].id == user_sourceA.id
    assert user_sources[0].order == Decimal("1.99999999999999999999")

    assert user_sources[1].id == user_sourceB.id
    assert user_sources[1].order == Decimal("2.00300000000000000000")


@pytest.mark.django_db
def test_export_user_source(data_fixture):
    builder = data_fixture.create_builder_application()
    integration = data_fixture.create_local_baserow_integration()

    user_source = data_fixture.create_user_source_with_first_type(
        application=builder, integration=integration, name="Test name"
    )

    app_auth_provider1 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source
    )
    app_auth_provider2 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source
    )

    exported = UserSourceHandler().export_user_source(user_source)

    assert exported == {
        "email_field_id": None,
        "id": exported["id"],
        "integration_id": integration.id,
        "name": "Test name",
        "name_field_id": None,
        "order": "1.00000000000000000000",
        "role_field_id": None,
        "table_id": None,
        "type": "local_baserow",
        "uid": AnyStr(),
        "auth_providers": [
            {
                "domain": None,
                "enabled": True,
                "id": app_auth_provider1.id,
                "password_field_id": None,
                "type": "local_baserow_password",
            },
            {
                "domain": None,
                "enabled": True,
                "id": app_auth_provider2.id,
                "password_field_id": None,
                "type": "local_baserow_password",
            },
        ],
    }


@pytest.mark.django_db
def test_import_user_source(data_fixture):
    builder = data_fixture.create_builder_application()
    integration = data_fixture.create_local_baserow_integration()

    TO_IMPORT = {
        "email_field_id": None,
        "id": 28,
        "integration_id": integration.id,
        "name": "Test name",
        "name_field_id": None,
        "order": "1.00000000000000000000",
        "table_id": None,
        "type": "local_baserow",
        "auth_providers": [
            {
                "domain": None,
                "enabled": True,
                "id": 42,
                "password_field_id": None,
                "type": "local_baserow_password",
            },
            {
                "domain": None,
                "enabled": True,
                "id": 43,
                "password_field_id": None,
                "type": "local_baserow_password",
            },
        ],
    }

    imported_instance = UserSourceHandler().import_user_source(
        builder, TO_IMPORT, defaultdict(MirrorDict)
    )

    assert imported_instance.integration_id == integration.id
    assert imported_instance.name == "Test name"

    assert imported_instance.auth_providers.count() == 2


@pytest.mark.django_db
def test_import_user_source_with_migrated_integration(data_fixture):
    builder = data_fixture.create_builder_application()
    integration = data_fixture.create_local_baserow_integration()

    TO_IMPORT = {
        "email_field_id": None,
        "id": 28,
        "integration_id": 42,
        "name": "Test name",
        "name_field_id": None,
        "order": "1.00000000000000000000",
        "table_id": None,
        "type": "local_baserow",
    }

    id_mapping = defaultdict(MirrorDict)
    id_mapping["integrations"] = {42: integration.id}

    imported_instance = UserSourceHandler().import_user_source(
        builder, TO_IMPORT, id_mapping
    )

    assert imported_instance.integration_id == integration.id


@pytest.mark.django_db
def test_export_then_import_user_source(data_fixture, stub_user_source_registry):
    """
    Basically test that we can duplicate a user source which can be problematic
    because of the unique uid.
    """

    builder = data_fixture.create_builder_application()
    integration = data_fixture.create_local_baserow_integration()

    first_user_source_type = list(user_source_type_registry.get_all())[0]

    def gen_uid(user_source):
        return f"{user_source.id}_test"

    old_gen_uid = first_user_source_type.gen_uid
    first_user_source_type.gen_uid = gen_uid

    user_source = data_fixture.create_user_source_with_first_type(
        application=builder, integration=integration, name="Test name"
    )

    app_auth_provider1 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source
    )
    app_auth_provider2 = data_fixture.create_app_auth_provider_with_first_type(
        user_source=user_source
    )

    exported = UserSourceHandler().export_user_source(user_source)

    imported_instance = UserSourceHandler().import_user_source(
        builder, exported, defaultdict(MirrorDict)
    )

    assert imported_instance.uid != user_source.uid
    assert imported_instance.uid == f"{imported_instance.id}_test"

    exported["uid"] = f"{user_source.id}_test"

    imported_instance = UserSourceHandler().import_user_source(
        builder, exported, defaultdict(MirrorDict)
    )

    first_user_source_type.gen_uid = old_gen_uid

    assert imported_instance.uid == f"{imported_instance.id}_test"


@pytest.mark.django_db
def test_get_default_user_role(data_fixture):
    """Ensure the get_default_user_role() returns the default user role."""

    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(
        application=application,
    )

    default_user_role = user_source.get_type().get_default_user_role(user_source)

    assert default_user_role == f"{DEFAULT_USER_ROLE_PREFIX}{user_source.id}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "roles_a,roles_b,expected_roles",
    [
        (
            [],
            [],
            [],
        ),
        (
            [],
            ["zig_role"],
            ["zig_role"],
        ),
        (
            ["foo_role"],
            [],
            ["foo_role"],
        ),
        (
            ["foo_role"],
            ["zig_role"],
            ["foo_role", "zig_role"],
        ),
        (
            ["foo_role", "bar_role"],
            ["zig_role", "zag_role"],
            ["bar_role", "foo_role", "zag_role", "zig_role"],
        ),
    ],
)
def test_get_all_roles_for_application_returns_user_roles(
    data_fixture,
    roles_a,
    roles_b,
    expected_roles,
):
    builder = data_fixture.create_builder_application()
    user_source_1 = data_fixture.create_user_source_with_first_type(application=builder)
    users_table_1 = data_fixture.create_database_table(name="test_users_1")
    role_field_1 = data_fixture.create_text_field(
        table=users_table_1, order=0, name="role", text_default=""
    )
    user_source_1.table = users_table_1
    user_source_1.role_field = role_field_1
    user_source_1.save()

    # Add some roles
    model = users_table_1.get_model()
    for role in roles_a:
        model.objects.create(**{f"field_{role_field_1.id}": role})

    user_source_2 = data_fixture.create_user_source_with_first_type(application=builder)
    users_table_2 = data_fixture.create_database_table(name="test_users_2")
    role_field_2 = data_fixture.create_text_field(
        table=users_table_2, order=0, name="role", text_default=""
    )
    user_source_2.table = users_table_2
    user_source_2.role_field = role_field_2
    user_source_2.save()

    # Add some roles
    model = users_table_2.get_model()
    for role in roles_b:
        model.objects.create(**{f"field_{role_field_2.id}": role})

    user_roles = UserSourceHandler().get_all_roles_for_application(builder)

    assert user_roles == expected_roles


@pytest.mark.django_db
def test_generate_update_user_count_chunk_queryset(data_fixture):
    builder = data_fixture.create_builder_application()

    ids_seen = []
    ids_expected = list(range(1, 11))
    user_source_type = list(user_source_type_registry.get_all())[0]
    user_sources = data_fixture.create_user_sources_with_primary_keys(
        user_source_type, ids_expected, application=builder
    )

    # Sanity-check that all of them don't have a cached user count.
    for user_source in user_sources:
        assert (
            user_source.get_type().get_user_count(user_source, update_if_uncached=False)
            is None
        )

    with freeze_time("2024-12-16 12:00"):
        chunk = list(
            UserSourceHandler()
            ._generate_update_user_count_chunk_queryset(user_source_type)
            .values_list("id", flat=True)
        )
        ids_seen.extend(chunk)
        assert chunk == [4, 8]

    with freeze_time("2024-12-16 12:15"):
        chunk = list(
            UserSourceHandler()
            ._generate_update_user_count_chunk_queryset(user_source_type)
            .values_list("id", flat=True)
        )
        ids_seen.extend(chunk)
        assert chunk == [1, 5, 9]

    with freeze_time("2024-12-16 12:30"):
        chunk = list(
            UserSourceHandler()
            ._generate_update_user_count_chunk_queryset(user_source_type)
            .values_list("id", flat=True)
        )
        ids_seen.extend(chunk)
        assert chunk == [2, 6, 10]

    with freeze_time("2024-12-16 12:45"):
        chunk = list(
            UserSourceHandler()
            ._generate_update_user_count_chunk_queryset(user_source_type)
            .values_list("id", flat=True)
        )
        ids_seen.extend(chunk)
        assert chunk == [3, 7]

    assert sorted(ids_seen) == ids_expected


@pytest.mark.django_db
def test_update_all_user_source_counts(stub_user_source_registry):
    # Calling each `update_user_count`.
    with stub_user_source_registry(update_user_count_return=lambda: 123):
        UserSourceHandler().update_all_user_source_counts()

    # When an exception raises, by default we won't propagate it.
    def mock_raise_update_user_count(user_source):
        raise Exception("An error has occurred.")

    with stub_user_source_registry(
        update_user_count_return=mock_raise_update_user_count
    ):
        UserSourceHandler().update_all_user_source_counts()

    # When an exception raises, we can make it propagate.
    with stub_user_source_registry(
        update_user_count_return=mock_raise_update_user_count
    ), pytest.raises(Exception) as exc:
        UserSourceHandler().update_all_user_source_counts(raise_on_error=True)
    assert str(exc.value) == "An error has occurred."


@pytest.mark.django_db
def test_update_all_user_source_counts_in_chunks(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(application=builder)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Email", "text"),
            ("Name", "text"),
            ("Role", "text"),
        ],
        rows=[
            ["jrmi@baserow.io", "Jérémie", ""],
            ["peter@baserow.io", "Peter", ""],
            ["afonso@baserow.io", "Afonso", ""],
            ["tsering@baserow.io", "Tsering", ""],
            ["evren@baserow.io", "Evren", ""],
        ],
    )
    email_field, name_field, role_field = fields

    user_source_type = list(user_source_type_registry.get_all())[0]
    user_sources = data_fixture.create_user_sources_with_primary_keys(
        user_source_type,
        list(range(1, 11)),
        application=builder,
        integration=integration,
        table=table,
        email_field=email_field,
        name_field=name_field,
        role_field=role_field,
    )

    def _count_user_sources_with_cached_value(
        user_sources: QuerySet[UserSource],
    ) -> int:
        with_cached_count = [
            user_source
            for user_source in user_sources
            if user_source.get_type().get_user_count(
                user_source, update_if_uncached=False
            )
            is not None
        ]
        return len(with_cached_count)

    # Sanity-check that all of them don't have a cached user count.
    assert _count_user_sources_with_cached_value(user_sources) == 0

    with freeze_time("2024-12-16 12:00"):
        UserSourceHandler().update_all_user_source_counts(update_in_chunks=True)
        assert _count_user_sources_with_cached_value(user_sources) == 2  # [4,8]

    with freeze_time("2024-12-16 12:15"):
        UserSourceHandler().update_all_user_source_counts(update_in_chunks=True)
        assert _count_user_sources_with_cached_value(user_sources) == 5  # [1,4,5,8,9]

    with freeze_time("2024-12-16 12:30"):
        UserSourceHandler().update_all_user_source_counts(update_in_chunks=True)
        assert (
            _count_user_sources_with_cached_value(user_sources) == 8
        )  # [1,2,4,5,6,8,9,10]

    with freeze_time("2024-12-16 12:45"):
        UserSourceHandler().update_all_user_source_counts(update_in_chunks=True)
        assert (
            _count_user_sources_with_cached_value(user_sources) == 10
        )  # [1,2,3,4,5,6,7,8,9,10]


@pytest.mark.django_db
def test_aggregate_user_counts(data_fixture):
    user = data_fixture.create_user()
    workspace1 = data_fixture.create_workspace(user=user)

    # Workspace1 has two builder applications, with two user sources,
    # pointing to the same table.
    builder1a = data_fixture.create_builder_application(workspace=workspace1)
    user_source1a = data_fixture.create_local_baserow_table_user_source(
        application=builder1a
    )
    builder1b = data_fixture.create_builder_application(workspace=workspace1)
    data_fixture.create_local_baserow_table_user_source(
        application=builder1b, table=user_source1a.table
    )

    # The table contains 5 rows, and is used twice, so the usage for both is 10.
    assert UserSourceHandler().aggregate_user_counts(workspace1) == 10

    workspace2 = data_fixture.create_workspace(user=user)
    builder2 = data_fixture.create_builder_application(workspace=workspace2)
    data_fixture.create_local_baserow_table_user_source(application=builder2)

    # The table contains 5 rows, and is used once, so the usage is 5.
    assert UserSourceHandler().aggregate_user_counts(workspace2) == 5

    # Globally, on this instance, we have a usage of 15.
    assert UserSourceHandler().aggregate_user_counts() == 15
