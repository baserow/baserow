from django.test import override_settings
from django.urls import reverse

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_200_OK

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.core.trash.handler import TrashHandler
from baserow.test_utils.pytest_conftest import (
    FakeDispatchContext,
    fake_import_formula,
)
from baserow_enterprise.automation.nodes.node_types import (
    LocalBaserowSemanticSearchActionNodeType,
)
from baserow_enterprise.integrations.local_baserow.models import (
    LocalBaserowSemanticSearch,
)
from baserow_enterprise.integrations.local_baserow.service_types import (
    LocalBaserowSemanticSearchServiceType,
)
from baserow_enterprise.semantic_search.exceptions import SemanticSearchNotAvailable
from baserow_enterprise.semantic_search.handler import SemanticSearchHandler
from baserow_enterprise.semantic_search.vector_table import EXACT_SEARCH_MAX_ROWS
from baserow_premium.license.exceptions import FeaturesNotAvailableError

from .utils import index

DOCUMENTS = [
    "How to reset your password",
    "Monthly budget meeting notes",
    "Recipe for a chocolate cake",
    "Password policy for employees",
]


@pytest.fixture
def searchable_table(data_fixture, semantic_search):
    user, token = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Document", "long_text"), ("Category", "text"), ("score", "number")],
        rows=[[document, "public", 7] for document in DOCUMENTS],
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    index(table)
    return user, token, table, fields, rows


def create_data_source(data_fixture, user, table, **kwargs):
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    return data_fixture.create_builder_data_source(
        user=user,
        page=page,
        service_model_class=LocalBaserowSemanticSearch,
        integration=integration,
        table=table,
        **kwargs,
    )


def dispatch_data_source(api_client, token, data_source):
    response = api_client.post(
        reverse(
            "api:builder:data_source:dispatch",
            kwargs={"data_source_id": data_source.id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    return response.json()


@pytest.mark.django_db
def test_dispatch_data_source(api_client, data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    data_source = create_data_source(
        data_fixture,
        user,
        table,
        search_query="'reset password'",
        max_results=2,
    )
    data_source.service.specific.included_fields.set([fields[0], fields[2]])

    result = dispatch_data_source(api_client, token, data_source)

    # A field named like another property of a result keeps its value.
    assert [
        (item["id"], item["row"]["Document"], item["row"]["score"])
        for item in result["results"]
    ] == [
        (rows[0].id, "How to reset your password", 7),
        (rows[3].id, "Password policy for employees", 7),
    ]
    assert set(result["results"][0]["row"]) == {"id", "Document", "score"}
    assert {item["matched_field"] for item in result["results"]} == {"Document"}
    first_score, second_score = [item["score"] for item in result["results"]]
    assert 0 < second_score < first_score <= 1
    # The maximum number of results is the end of the results.
    assert result["has_next_page"] is False


@pytest.mark.django_db
def test_dispatch_with_filters_and_minimum_similarity(
    api_client, data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    table.get_model().objects.filter(id=rows[0].id).update(
        **{fields[1].db_column: "private"}
    )
    data_source = create_data_source(
        data_fixture,
        user,
        table,
        search_query="'reset password'",
        min_similarity=0.3,
    )
    data_fixture.create_local_baserow_table_service_filter(
        service=data_source.service,
        field=fields[1],
        type="equal",
        value="'public'",
        order=0,
    )

    result = dispatch_data_source(api_client, token, data_source)

    assert [item["row"]["Document"] for item in result["results"]] == [
        "Password policy for employees"
    ]


@pytest.mark.django_db
def test_dispatch_automation_node(data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    workflow = data_fixture.create_automation_workflow(user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=workflow.automation
    )
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowSemanticSearchActionNodeType.type,
        service_kwargs={
            "integration": integration,
            "table": table,
            "search_query": "'chocolate cake'",
            "max_results": 1,
        },
    )

    result = node.get_type().dispatch(
        node, AutomationDispatchContext(node.workflow, None)
    )

    assert [item["row"]["Document"] for item in result.data["results"]] == [
        "Recipe for a chocolate cake"
    ]


@pytest.mark.django_db
def test_search_large_tables_with_the_vector_index(data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Document", "text")], rows=[["chocolate cake"]]
    )
    model = table.get_model()
    model.objects.bulk_create(
        [
            model(**{fields[0].db_column: f"document {number}"})
            for number in range(EXACT_SEARCH_MAX_ROWS)
        ]
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    index(table, seconds=600)

    matches = SemanticSearchHandler().search(
        [fields[0]], "chocolate cake", model.objects.all(), limit=1
    )

    assert [match.row_id for match in matches] == [rows[0].id]


@pytest.mark.django_db
def test_search_multiple_fields(data_fixture, enterprise_data_fixture, semantic_search):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Title", "text"), ("Body", "long_text"), ("Other", "text")],
        rows=[
            ["Holiday policy", "Employees get 25 days off", "dogs"],
            ["Office rules", "Dogs are welcome on Fridays", "holiday"],
        ],
    )
    title, body, other = fields
    for field in [title, body]:
        FieldHandler().update_field(user, field, semantic_search_enabled=True)
    index(table)
    service = enterprise_data_fixture.create_local_baserow_semantic_search_service(
        integration=data_fixture.create_local_baserow_integration(user=user),
        table=table,
        min_similarity=0.1,
    )

    def search(query):
        service.search_query = f"'{query}'"
        service.save()
        result = service.get_type().dispatch(
            service, FakeDispatchContext(workspace=table.database.workspace)
        )
        return [
            (item["row"]["Title"], item["matched_field"])
            for item in result.data["results"]
        ]

    # Without chosen fields, all fields with semantic search are searched, and each
    # row is returned once with the field that matches best.
    assert search("holiday") == [("Holiday policy", "Title")]
    assert search("dogs") == [("Office rules", "Body")]

    service.search_all_fields = False
    service.search_fields.set([title])
    assert search("dogs") == []


@pytest.mark.django_db
def test_dispatch_misconfigured(data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    other_table = data_fixture.create_database_table(user=user)
    workflow = data_fixture.create_automation_workflow(user)
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowSemanticSearchActionNodeType.type,
        service_kwargs={"table": other_table, "search_query": "'cake'"},
    )
    service = node.service.specific
    dispatch_context = AutomationDispatchContext(node.workflow, None)

    # The table has no fields with semantic search.
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        node.get_type().dispatch(node, dispatch_context)

    service.table = table
    service.search_all_fields = False
    service.save()
    service.search_fields.set([fields[0]])
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=False)
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        node.get_type().dispatch(node, dispatch_context)


@pytest.mark.django_db
def test_search_never_widens_when_the_chosen_fields_are_gone(
    data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    left_out = FieldHandler().update_field(
        user, fields[1], semantic_search_enabled=True
    )
    integration = data_fixture.create_local_baserow_integration(user=user)
    service_type = service_type_registry.get(LocalBaserowSemanticSearchServiceType.type)
    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "integration_id": integration.id,
            "search_field_ids": [fields[0].id],
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    assert service.search_all_fields is False

    FieldHandler().delete_field(user, fields[0])
    TrashHandler.permanently_delete(fields[0])
    service = LocalBaserowSemanticSearch.objects.get(id=service.id)

    # The field that was left out on purpose isn't searched instead.
    assert service.search_field_ids == []
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        service_type.get_fields_to_search(service)

    values = service_type.prepare_values({"search_field_ids": []}, user, service)
    service = ServiceHandler().update_service(service_type, service, **values).service
    assert [field.id for field in service_type.get_fields_to_search(service)] == [
        left_out.id
    ]


@pytest.mark.django_db
def test_edits_drop_chosen_fields_that_cant_be_searched_anymore(
    data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    FieldHandler().update_field(user, fields[1], semantic_search_enabled=True)
    integration = data_fixture.create_local_baserow_integration(user=user)
    service_type = service_type_registry.get(LocalBaserowSemanticSearchServiceType.type)
    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "integration_id": integration.id,
            "search_field_ids": [fields[0].id],
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=False)

    # The form still sends the stale field along with the new choice.
    values = service_type.prepare_values(
        {"search_field_ids": [fields[0].id, fields[1].id]}, user, service
    )

    assert values["search_field_ids"] == [fields[1].id]
    assert values["search_all_fields"] is False


@pytest.mark.django_db
def test_requires_license_and_embeddings_service(
    data_fixture, enterprise_data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    workflow = data_fixture.create_automation_workflow(user)
    node_type = LocalBaserowSemanticSearchActionNodeType()

    def create_node():
        return AutomationNodeService().create_node(
            user,
            node_type,
            workflow,
            reference_node_id=workflow.get_trigger().id,
            position="south",
            output="",
        )

    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        assert node_type.is_deactivated(workflow.automation.workspace)
        with pytest.raises(SemanticSearchNotAvailable):
            create_node()

    node = create_node()

    enterprise_data_fixture.delete_all_licenses()
    assert node_type.is_deactivated(workflow.automation.workspace)
    with pytest.raises(FeaturesNotAvailableError):
        create_node()
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        node.get_type().dispatch(node, AutomationDispatchContext(node.workflow, None))


@pytest.mark.django_db
def test_only_semantic_search_fields_of_the_table_can_be_chosen(
    data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    integration = data_fixture.create_local_baserow_integration(user=user)
    service_type = service_type_registry.get(LocalBaserowSemanticSearchServiceType.type)

    with pytest.raises(ValidationError):
        service_type.prepare_values(
            {"table_id": table.id, "search_field_ids": [fields[1].id]}, user
        )
    with pytest.raises(ValidationError):
        service_type.prepare_values(
            {
                "table_id": table.id,
                "included_field_ids": [data_fixture.create_text_field().id],
            },
            user,
        )

    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "search_field_ids": [fields[0].id],
            "included_field_ids": [fields[1].id],
            "integration_id": integration.id,
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    assert service.search_field_ids == [fields[0].id]
    assert service.included_field_ids == [fields[1].id]

    # The fields belong to the previous table.
    other_table = data_fixture.create_database_table(database=table.database)
    values = service_type.prepare_values({"table_id": other_table.id}, user, service)
    service = ServiceHandler().update_service(service_type, service, **values).service
    assert service.search_field_ids == []
    assert service.search_all_fields is True
    assert service.included_field_ids == []


@pytest.mark.django_db
def test_schema_nests_the_row(enterprise_data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    service = enterprise_data_fixture.create_local_baserow_semantic_search_service(
        table=table
    )
    service.included_fields.set([fields[1]])

    schema = service.get_type().generate_schema(service)

    assert schema["type"] == "array"
    assert set(schema["items"]["properties"]) == {
        "id",
        "row",
        "score",
        "matched_field",
    }
    assert set(schema["items"]["properties"]["row"]["properties"]) == {
        "id",
        fields[1].db_column,
    }


@pytest.mark.django_db
def test_paths_to_row_values_are_imported(searchable_table):
    user, token, table, fields, rows = searchable_table
    service_type = LocalBaserowSemanticSearchServiceType()
    id_mapping = {"database_fields": {fields[0].id: 123}}

    assert service_type.import_path(
        ["0", "row", fields[0].db_column, "value"], id_mapping
    ) == ["0", "row", "field_123", "value"]
    assert service_type.import_path(["0", "score"], id_mapping) == ["0", "score"]
    assert service_type.extract_properties(None, ["row", fields[0].db_column]) == [
        fields[0].db_column
    ]


@pytest.mark.django_db
def test_export_import_service(data_fixture, enterprise_data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    integration = data_fixture.create_local_baserow_integration(user=user)
    service = enterprise_data_fixture.create_local_baserow_semantic_search_service(
        integration=integration, table=table, search_all_fields=False
    )
    service.search_fields.set([fields[0]])
    service.included_fields.set([fields[1]])
    service_type = service.get_type()

    serialized = service_type.export_serialized(service)
    assert serialized["search_field_ids"] == [fields[0].id]
    assert serialized["included_field_ids"] == [fields[1].id]

    other_table = data_fixture.create_database_table(database=table.database)
    new_field = data_fixture.create_text_field(table=other_table)
    new_service = service_type.import_serialized(
        integration,
        serialized,
        {
            "database_tables": {table.id: other_table.id},
            "database_fields": {fields[0].id: new_field.id},
        },
        import_formula=fake_import_formula,
    )

    assert new_service.table_id == other_table.id
    assert new_service.search_field_ids == [new_field.id]
    assert new_service.search_all_fields is False
    # An unmapped field isn't kept, because it can belong to another workspace.
    assert new_service.included_field_ids == []


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)
def test_common_words_dont_bypass_the_minimum_similarity(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(table=table, name="Notes")
    FieldHandler().update_field(user, field, semantic_search_enabled=True)
    for text in ["Cats and dogs", "Mix flour and sugar", "Invoice XK42 is overdue"]:
        api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table.id}),
            {f"field_{field.id}": text},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    queryset = table.get_model().objects.all()
    handler = SemanticSearchHandler()

    def search(query, min_similarity=None):
        return [
            (getattr(queryset.get(id=match.row_id), field.db_column), match.similarity)
            for match in handler.search(
                [field], query, queryset, limit=3, min_similarity=min_similarity
            )
        ]

    # "and" is in two rows, but rows only match by their words if they contain
    # all the words of the query.
    assert [text for text, _ in search("dogs and cats", min_similarity=0.5)] == [
        "Cats and dogs"
    ]
    matches = search("XK42")
    assert matches[0][0] == "Invoice XK42 is overdue"
    assert all(similarity is not None for _, similarity in matches)
