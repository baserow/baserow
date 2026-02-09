import pytest

from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFilter,
)
from baserow.contrib.integrations.migrations.helpers.migrate_local_baserow_table_service_filter_formulas_to_value_is_formula import (  # noqa: E501
    value_parses_as_formula,
)
from baserow.contrib.integrations.migrations.helpers.migrate_local_baserow_table_service_filter_values_to_formulas import (  # noqa: E501
    FIELD_TYPE_FILTERS_TO_MIGRATE,
    reduce_to_filter_types_to_migrate,
)


def _generate_filter_for_every_compatible_field_type(filter_model, **filter_kwargs):
    filter_for_every_compatible_field_type = []
    for i, filter_type in enumerate(view_filter_type_registry.get_all()):
        for compatible_field_type in filter_type.compatible_field_types:
            if callable(compatible_field_type):
                # Catch 22: I don't have a field to pass to the callable.
                continue
            field_type = field_type_registry.get(compatible_field_type)
            if "field" not in filter_kwargs:
                filter_kwargs["field"] = field_type.model_class(pk=i)
            filter_kwargs["order"] = i
            filter_kwargs["type"] = filter_type.type
            filter_for_every_compatible_field_type.append(filter_model(**filter_kwargs))
    return filter_for_every_compatible_field_type


@pytest.mark.django_db
def test_0003_migrate_local_baserow_table_service_filter_values_to_formulas_reduce_to_filter_types_to_migrate():  # noqa: E501
    filter_for_every_compatible_field_type = (
        _generate_filter_for_every_compatible_field_type(LocalBaserowTableServiceFilter)
    )
    reduced_filter_list = reduce_to_filter_types_to_migrate(
        filter_for_every_compatible_field_type
    )
    for reduced_filter in reduced_filter_list:
        field_type = field_type_registry.get_by_model(reduced_filter.field)
        assert field_type.type in FIELD_TYPE_FILTERS_TO_MIGRATE
        assert reduced_filter.type in FIELD_TYPE_FILTERS_TO_MIGRATE[field_type.type]


@pytest.mark.once_per_day_in_ci
def test_0003_migrate_local_baserow_table_service_filter_values_to_formulas_forwards(
    migrator, teardown_table_metadata
):
    migrate_from = [
        ("builder", "0001_squashed_0038_initial"),
        ("database", "0150_formulafield_duration_format_and_more"),
        ("integrations", "0002_migrate_local_baserow_service_value_to_formulafield"),
    ]
    migrate_to = [
        (
            "integrations",
            "0003_migrate_local_baserow_table_service_filter_values_to_formulas",
        )
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    Database = old_state.apps.get_model("database", "Database")
    TextField = old_state.apps.get_model("database", "TextField")
    Table = old_state.apps.get_model("database", "Table")
    LocalBaserowIntegration = old_state.apps.get_model(
        "integrations", "LocalBaserowIntegration"
    )
    LocalBaserowListRows = old_state.apps.get_model(
        "integrations", "LocalBaserowListRows"
    )
    LocalBaserowTableServiceFilter = old_state.apps.get_model(
        "integrations", "LocalBaserowTableServiceFilter"
    )

    workspace = Workspace.objects.create(name="Workspace")
    database = Database.objects.create(
        order=1,
        name="Database",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Database),
    )
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    table = Table.objects.create(database=database, name="Table", order=1)
    field = TextField.objects.create(
        table=table, order=1, content_type=ContentType.objects.get_for_model(TextField)
    )
    integration = LocalBaserowIntegration.objects.create(
        application=builder,
        content_type=ContentType.objects.get_for_model(LocalBaserowIntegration),
    )
    service = LocalBaserowListRows.objects.create(
        integration=integration,
        content_type=ContentType.objects.get_for_model(LocalBaserowListRows),
    )

    LocalBaserowTableServiceFilter.objects.bulk_create(
        _generate_filter_for_every_compatible_field_type(
            LocalBaserowTableServiceFilter,
            **{
                "field": field,
                "value": "dogs",
                "service": service,
            },
        )
    )

    new_state = migrator.migrate(migrate_to)

    LocalBaserowTableServiceFilter = new_state.apps.get_model(
        "integrations", "LocalBaserowTableServiceFilter"
    )

    all_filters = LocalBaserowTableServiceFilter.objects.all()

    filters_which_migrated = reduce_to_filter_types_to_migrate(all_filters)
    for filter_which_migrated in filters_which_migrated:
        assert filter_which_migrated.value == "'dogs'", (
            f"Filter type={filter_which_migrated.type} field={filter_which_migrated.field} did not migrate correctly."
        )  # noqa: E501

    filters_which_did_not_migrate = [
        service_filter
        for service_filter in all_filters
        if service_filter not in filters_which_migrated
    ]
    for filter_which_did_not_migrate in filters_which_did_not_migrate:
        assert filter_which_did_not_migrate.value != "'dogs'", (
            f"Filter type={filter_which_did_not_migrate.type} field={filter_which_did_not_migrate.field} migrated when it should not have."
        )  # noqa: E501


@pytest.mark.once_per_day_in_ci
def test_0004_migrate_local_baserow_getrow_list_rows_search_query_to_formulas_forwards(
    migrator, teardown_table_metadata
):
    migrate_from = [
        ("builder", "0001_squashed_0038_initial"),
        ("database", "0150_formulafield_duration_format_and_more"),
        (
            "integrations",
            "0003_migrate_local_baserow_table_service_filter_values_to_formulas",
        ),
    ]
    migrate_to = [
        (
            "integrations",
            "0004_migrate_local_baserow_getrow_list_rows_search_query_to_formulas",
        )
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    LocalBaserowIntegration = old_state.apps.get_model(
        "integrations", "LocalBaserowIntegration"
    )
    LocalBaserowGetRow = old_state.apps.get_model("integrations", "LocalBaserowGetRow")
    LocalBaserowListRows = old_state.apps.get_model(
        "integrations", "LocalBaserowListRows"
    )

    workspace = Workspace.objects.create(name="Workspace")
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    integration = LocalBaserowIntegration.objects.create(
        application=builder,
        content_type=ContentType.objects.get_for_model(LocalBaserowIntegration),
    )
    LocalBaserowGetRow.objects.create(
        integration=integration,
        search_query="bunnies",
        content_type=ContentType.objects.get_for_model(LocalBaserowListRows),
    )
    LocalBaserowListRows.objects.create(
        integration=integration,
        search_query="horses",
        content_type=ContentType.objects.get_for_model(LocalBaserowListRows),
    )

    new_state = migrator.migrate(migrate_to)

    LocalBaserowGetRow = new_state.apps.get_model("integrations", "LocalBaserowGetRow")
    LocalBaserowListRows = new_state.apps.get_model(
        "integrations", "LocalBaserowListRows"
    )

    get_row_service = LocalBaserowGetRow.objects.get()
    assert get_row_service.search_query == "'bunnies'"

    list_rows_service = LocalBaserowListRows.objects.get()
    assert list_rows_service.search_query == "'horses'"


@pytest.mark.once_per_day_in_ci
def test_0006_migrate_local_baserow_table_service_filter_formulas_to_value_is_formula_forwards(  # noqa: E501
    migrator, teardown_table_metadata
):
    migrate_from = [
        ("builder", "0001_squashed_0038_initial"),
        ("database", "0150_formulafield_duration_format_and_more"),
        (
            "integrations",
            "0005_add_localbaserowtableservicefilter_value_is_formula",
        ),
    ]
    migrate_to = [
        (
            "integrations",
            "0006_migrate_local_baserow_table_service_filter_formulas_to_value_is_formula",
        )
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Builder = old_state.apps.get_model("builder", "Builder")
    Database = old_state.apps.get_model("database", "Database")
    TextField = old_state.apps.get_model("database", "TextField")
    Table = old_state.apps.get_model("database", "Table")
    LocalBaserowIntegration = old_state.apps.get_model(
        "integrations", "LocalBaserowIntegration"
    )
    LocalBaserowListRows = old_state.apps.get_model(
        "integrations", "LocalBaserowListRows"
    )
    LocalBaserowTableServiceFilter = old_state.apps.get_model(
        "integrations", "LocalBaserowTableServiceFilter"
    )

    workspace = Workspace.objects.create(name="Workspace")
    database = Database.objects.create(
        order=1,
        name="Database",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Database),
    )
    builder = Builder.objects.create(
        order=2,
        name="Builder",
        workspace=workspace,
        content_type=ContentType.objects.get_for_model(Builder),
    )
    table = Table.objects.create(database=database, name="Table", order=1)
    field = TextField.objects.create(
        table=table, order=1, content_type=ContentType.objects.get_for_model(TextField)
    )
    integration = LocalBaserowIntegration.objects.create(
        application=builder,
        content_type=ContentType.objects.get_for_model(LocalBaserowIntegration),
    )
    service = LocalBaserowListRows.objects.create(
        integration=integration,
        content_type=ContentType.objects.get_for_model(LocalBaserowListRows),
    )

    values_to_test = [
        "",  # empty strings shouldn't become formulas
        "123",  # integers (numeric / link row / bools / etc) shouldn't become formulas
        "plain text",  # plain text shouldn't become formulas
        "Europe/London?2024-02-01",  # dates shouldn't become formulas
        "get('page_parameter.id')",  # valid formula
        "concat('ID', get('page_parameter.id'))",  # concat formula
    ]
    bulk_filters_to_create = [
        LocalBaserowTableServiceFilter(
            field=field, service=service, order=i, value=value
        )
        for i, value in enumerate(values_to_test)
    ]
    LocalBaserowTableServiceFilter.objects.bulk_create(bulk_filters_to_create)

    new_state = migrator.migrate(migrate_to)

    LocalBaserowTableServiceFilter = new_state.apps.get_model(
        "integrations", "LocalBaserowTableServiceFilter"
    )

    for service_filter in LocalBaserowTableServiceFilter.objects.all():
        if value_parses_as_formula(service_filter.value):
            assert service_filter.value_is_formula is True, (
                "A valid formula was detected, but value_is_formula was not set to True."
            )
        else:
            assert service_filter.value_is_formula is False, (
                "A invalid formula was detected, but value_is_formula was not set to False."
            )  # noqa: E501
