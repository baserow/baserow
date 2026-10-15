import json
import random
from unittest.mock import patch

from django.db import connection
from django.http import HttpRequest
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_200_OK

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.data_providers.data_provider_types import (
    PreviousNodeProviderType,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.builder.data_providers.data_provider_types import (
    CurrentRecordDataProviderType,
)
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.graph.types import GraphPointPosition
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


def create_integration(data_fixture, user, table):
    # The table is read through the integration, so they share a workspace.
    builder = data_fixture.create_builder_application(
        user=user, workspace=table.database.workspace
    )
    return data_fixture.create_local_baserow_integration(user=user, application=builder)


def create_data_source(data_fixture, user, table, **kwargs):
    builder = data_fixture.create_builder_application(
        user=user, workspace=table.database.workspace
    )
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
        include_all_fields=False,
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
    assert all(0 < item["similarity"] <= 1 for item in result["results"])
    # The maximum number of results is the end of the results.
    assert result["has_next_page"] is False


def create_published_page_using_fields(
    data_fixture, user, table, fields, result_properties=()
):
    builder = data_fixture.create_builder_application(
        user=user, workspace=table.database.workspace
    )
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    page = data_fixture.create_builder_page(builder=published_builder)
    data_source = data_fixture.create_builder_data_source(
        page=page,
        service_model_class=LocalBaserowSemanticSearch,
        integration=data_fixture.create_local_baserow_integration(
            user=user, application=published_builder
        ),
        table=table,
        search_query="'reset password'",
        max_results=2,
    )
    for field in fields:
        data_fixture.create_builder_heading_element(
            page=page,
            value=f"get('data_source.{data_source.id}.0.row.{field.db_column}')",
        )
    for name in result_properties:
        data_fixture.create_builder_heading_element(
            page=page, value=f"get('data_source.{data_source.id}.0.{name}')"
        )
    return page, data_source


def dispatch_published_page(api_client, page):
    return api_client.post(
        reverse("api:builder:domains:public_dispatch_all", kwargs={"page_id": page.id}),
        {},
        format="json",
    )


@pytest.mark.django_db
def test_published_page_only_receives_the_used_row_values(
    api_client, data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    page, data_source = create_published_page_using_fields(
        data_fixture, user, table, [fields[0]]
    )

    response = dispatch_published_page(api_client, page)

    assert response.status_code == HTTP_200_OK
    results = response.json()[str(data_source.id)]["results"]
    assert [item["row"] for item in results] == [
        {"Document": "How to reset your password"},
        {"Document": "Password policy for employees"},
    ]
    assert [item["id"] for item in results] == [rows[0].id, rows[3].id]
    # The matched field can be one that the page doesn't show.
    assert all(set(item) == {"id", "row"} for item in results)


@pytest.mark.django_db
def test_published_page_receives_the_used_result_properties(
    api_client, data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    page, data_source = create_published_page_using_fields(
        data_fixture, user, table, [], ["score", "matched_field"]
    )

    response = dispatch_published_page(api_client, page)

    assert response.status_code == HTTP_200_OK
    results = response.json()[str(data_source.id)]["results"]
    assert [set(item) for item in results] == [
        {"id", "row", "score", "matched_field"}
    ] * 2
    assert all(0 < item["score"] <= 1 for item in results)
    assert results[0]["matched_field"] == fields[0].name
    assert results[0]["row"] == {}


@pytest.mark.django_db
def test_only_the_used_values_are_loaded(api_client, data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    page, data_source = create_published_page_using_fields(
        data_fixture, user, table, [fields[0], fields[1]]
    )
    # A used field can be deleted after the page was made.
    FieldHandler().delete_field(user, fields[1])
    TrashHandler.permanently_delete(fields[1])

    with CaptureQueriesContext(connection) as queries:
        response = dispatch_published_page(api_client, page)

    assert response.status_code == HTTP_200_OK
    assert response.json()[str(data_source.id)]["results"][0]["row"] == {
        "Document": "How to reset your password"
    }
    sql = " ".join(query["sql"] for query in queries.captured_queries)
    assert f'"{fields[0].db_column}"' in sql
    assert f'"{fields[2].db_column}"' not in sql


@pytest.mark.django_db
def test_action_uses_the_values_of_the_clicked_row(data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    data_source = create_data_source(
        data_fixture,
        user,
        table,
        search_query="'reset password'",
        max_results=2,
    )
    page = data_source.page
    repeat = data_fixture.create_builder_repeat_element(
        page=page, data_source=data_source
    )
    button = data_fixture.create_builder_button_element(
        page=page, reference_element=repeat, position=GraphPointPosition.CHILD
    )
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=button, event=EventTypes.CLICK, user=user
    )
    request = HttpRequest()
    request.user = user
    # The second result was clicked.
    request.data = {
        "metadata": json.dumps(
            {"current_record": {"index_path": [1], "record_id": rows[3].id}}
        )
    }
    dispatch_context = BuilderDispatchContext(
        request, page, workflow_action, only_expose_public_allowed_properties=False
    )

    value = CurrentRecordDataProviderType().get_data_chunk(
        dispatch_context, ["row", fields[0].db_column]
    )

    assert value == "Password policy for employees"


@pytest.mark.django_db
def test_pages_continue_where_the_previous_page_ended(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    words = "apple banana cherry grape lemon mango melon peach pear plum".split()
    generator = random.Random(2)
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[("Notes", "text")],
        rows=[
            [" ".join(generator.choices(words, k=generator.randint(2, 6)))]
            for _ in range(40)
        ],
    )
    FieldHandler().update_field(user, fields[0], semantic_search_enabled=True)
    index(table)
    data_source = create_data_source(
        data_fixture, user, table, search_query="'apple banana'", max_results=30
    )
    url = reverse(
        "api:builder:data_source:dispatch", kwargs={"data_source_id": data_source.id}
    )

    def get_row_ids(offset, count):
        response = api_client.post(
            f"{url}?offset={offset}&count={count}",
            {},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        return [item["id"] for item in response.json()["results"]]

    paged_row_ids = []
    for offset in range(0, 30, 5):
        paged_row_ids += get_row_ids(offset, 5)

    assert paged_row_ids == get_row_ids(0, 30)


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
    workflow = data_fixture.create_automation_workflow(
        user,
        automation=data_fixture.create_automation_application(
            user=user, workspace=table.database.workspace
        ),
    )
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
def test_filtered_rows_are_found_beyond_the_nearest_hidden_ones(
    data_fixture, semantic_search
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Document", "text"), ("Visible", "boolean")], rows=[]
    )
    document, visible = fields
    model = table.get_model()
    # More visible rows than are searched exactly, but all of them less similar
    # than the hidden rows that the vector index returns first.
    model.objects.bulk_create(
        [model(**{document.db_column: "chocolate cake"}) for _ in range(1100)]
        + [
            model(**{document.db_column: "chocolate soup", visible.db_column: True})
            for _ in range(EXACT_SEARCH_MAX_ROWS + 100)
        ]
    )
    FieldHandler().update_field(user, document, semantic_search_enabled=True)
    index(table, seconds=600)

    matches = SemanticSearchHandler().search(
        [document],
        "chocolate cake",
        model.objects.filter(**{visible.db_column: True}),
        limit=10,
    )

    assert len(matches) == 10
    assert all(
        getattr(model.objects.get(id=match.row_id), visible.db_column)
        for match in matches
    )


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
        integration=create_integration(data_fixture, user, table),
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
def test_incompatible_fields_are_searched_again_when_compatible(
    data_fixture, enterprise_data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    document, category, score = fields
    formula = FieldHandler().create_field(
        user, table, "formula", name="Copy", formula="field('Category')"
    )
    FieldHandler().update_field(
        user, formula, formula="field('Category')", semantic_search_enabled=True
    )
    integration = create_integration(data_fixture, user, table)
    all_fields = enterprise_data_fixture.create_local_baserow_semantic_search_service(
        integration=integration, table=table
    )
    chosen = enterprise_data_fixture.create_local_baserow_semantic_search_service(
        integration=integration, table=table, search_all_fields=False
    )
    chosen.search_fields.set([formula])
    service_type = chosen.get_type()

    # The result of the formula becomes a number, so it's incompatible.
    FieldHandler().update_field(user, category, new_type_name="number")

    assert [field.id for field in service_type.get_fields_to_search(all_fields)] == [
        document.id
    ]
    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as error:
        service_type.get_fields_to_search(chosen)
    assert "aren't text anymore" in str(error.value)

    FieldHandler().update_field(user, category, new_type_name="text")

    # It stayed chosen, so it's searched again.
    assert [field.id for field in service_type.get_fields_to_search(chosen)] == [
        formula.id
    ]


@pytest.mark.django_db
def test_search_never_widens_when_the_chosen_fields_are_gone(
    data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    left_out = FieldHandler().update_field(
        user, fields[1], semantic_search_enabled=True
    )
    integration = create_integration(data_fixture, user, table)
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

    # Also not with another change, which sends the same empty choice.
    values = service_type.prepare_values({"search_field_ids": []}, user, service)
    service = ServiceHandler().update_service(service_type, service, **values).service
    assert service.search_all_fields is False

    # Choosing a field and clearing the choice again searches all of them.
    for search_field_ids in ([left_out.id], []):
        values = service_type.prepare_values(
            {"search_field_ids": search_field_ids}, user, service
        )
        service = (
            ServiceHandler().update_service(service_type, service, **values).service
        )
    assert [field.id for field in service_type.get_fields_to_search(service)] == [
        left_out.id
    ]


@pytest.mark.django_db
def test_other_values_arent_returned_when_the_chosen_fields_are_gone(
    data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    integration = create_integration(data_fixture, user, table)
    service_type = service_type_registry.get(LocalBaserowSemanticSearchServiceType.type)
    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "integration_id": integration.id,
            "search_query": "'reset password'",
            "max_results": 1,
            "included_field_ids": [fields[1].id],
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    assert service.include_all_fields is False

    def get_row():
        service = LocalBaserowSemanticSearch.objects.get(id=service_id)
        dispatch_context = FakeDispatchContext(workspace=table.database.workspace)
        result = ServiceHandler().dispatch_service(service, dispatch_context)
        return result.data["results"][0]["row"]

    service_id = service.id
    assert get_row() == {"id": rows[0].id, "Category": "public"}

    FieldHandler().delete_field(user, fields[1])
    TrashHandler.permanently_delete(fields[1])

    # The fields that were left out on purpose aren't returned instead.
    assert get_row() == {"id": rows[0].id}

    # Also not with another change, which sends the same empty choice.
    service = LocalBaserowSemanticSearch.objects.get(id=service_id)
    values = service_type.prepare_values({"included_field_ids": []}, user, service)
    ServiceHandler().update_service(service_type, service, **values)
    assert get_row() == {"id": rows[0].id}

    # Choosing a field and clearing the choice again returns all of them.
    for included_field_ids in ([fields[0].id], []):
        service = LocalBaserowSemanticSearch.objects.get(id=service_id)
        values = service_type.prepare_values(
            {"included_field_ids": included_field_ids}, user, service
        )
        ServiceHandler().update_service(service_type, service, **values)
    assert set(get_row()) == {"id", "Document", "score"}


@pytest.mark.django_db
def test_restored_fields_arent_chosen_again(data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    category = FieldHandler().update_field(
        user, fields[1], semantic_search_enabled=True
    )
    integration = create_integration(data_fixture, user, table)
    service_type = service_type_registry.get(LocalBaserowSemanticSearchServiceType.type)
    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "integration_id": integration.id,
            "search_field_ids": [category.id],
            "included_field_ids": [category.id],
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)

    FieldHandler().delete_field(user, category)
    values = service_type.prepare_values(
        {"search_field_ids": [fields[0].id], "included_field_ids": [fields[2].id]},
        user,
        service,
    )
    ServiceHandler().update_service(service_type, service, **values)
    TrashHandler.restore_item(user, "field", category.id)

    service = LocalBaserowSemanticSearch.objects.get(id=service.id)
    assert service.search_field_ids == [fields[0].id]
    assert service.included_field_ids == [fields[2].id]


@pytest.mark.django_db
def test_edits_keep_chosen_fields_that_cant_be_searched_anymore(
    data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    FieldHandler().update_field(user, fields[1], semantic_search_enabled=True)
    integration = create_integration(data_fixture, user, table)
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

    # The form still sends the field that can't be searched along with the new
    # choice, also with the edits after it.
    for _ in range(2):
        values = service_type.prepare_values(
            {"search_field_ids": [fields[0].id, fields[1].id]}, user, service
        )
        service = (
            ServiceHandler().update_service(service_type, service, **values).service
        )

    assert service.search_field_ids == [fields[0].id, fields[1].id]
    assert service.search_all_fields is False
    # It isn't searched, until its semantic search is enabled again.
    assert [field.id for field in service_type.get_fields_to_search(service)] == [
        fields[1].id
    ]


@pytest.mark.django_db
def test_automation_node_requires_license_and_embeddings_service(
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


@pytest.fixture
def page_with_data_sources(data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    semantic_search = create_data_source(
        data_fixture, user, table, search_query="'reset password'", max_results=1
    )
    list_rows = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=semantic_search.page,
        table=table,
        integration=semantic_search.service.integration,
    )
    return user, token, semantic_search, list_rows


@pytest.mark.django_db
def test_data_source_requires_license_and_embeddings_service(
    enterprise_data_fixture, page_with_data_sources
):
    user, token, data_source, list_rows = page_with_data_sources
    service_type = service_type_registry.get(LocalBaserowSemanticSearchServiceType.type)

    with override_settings(BASEROW_EMBEDDINGS_API_URL=""):
        with pytest.raises(SemanticSearchNotAvailable):
            DataSourceService().create_data_source(
                user, page=data_source.page, service_type=service_type
            )

    enterprise_data_fixture.delete_all_licenses()

    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().create_data_source(
            user, page=data_source.page, service_type=service_type
        )
    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().update_data_source(
            user, data_source, service_type=service_type, max_results=2
        )
    with pytest.raises(FeaturesNotAvailableError):
        DataSourceService().dispatch_data_source(
            user,
            data_source,
            BuilderDispatchContext(
                HttpRequest(),
                data_source.page,
                only_expose_public_allowed_properties=False,
            ),
        )


@pytest.mark.django_db
def test_other_data_sources_of_the_page_work_without_license(
    api_client, enterprise_data_fixture, page_with_data_sources
):
    user, token, data_source, list_rows = page_with_data_sources
    enterprise_data_fixture.delete_all_licenses()

    response = api_client.post(
        reverse(
            "api:builder:data_source:dispatch-all",
            kwargs={"page_id": data_source.page_id},
        ),
        {},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    results = response.json()
    assert "_error" in results[str(data_source.id)]
    assert len(results[str(list_rows.id)]["results"]) == 4


@pytest.mark.django_db
@override_settings(BASEROW_SEMANTIC_SEARCH_MAX_RESULTS=25)
def test_settings_tell_the_editor_the_maximum_results(api_client, semantic_search):
    response = api_client.get(reverse("api:settings:get"))

    assert response.status_code == HTTP_200_OK
    assert response.json()["semantic_search"] == {"available": True, "max_results": 25}


@pytest.mark.django_db
def test_only_semantic_search_fields_of_the_table_can_be_chosen(
    data_fixture, searchable_table
):
    user, token, table, fields, rows = searchable_table
    integration = create_integration(data_fixture, user, table)
    service_type = service_type_registry.get(LocalBaserowSemanticSearchServiceType.type)

    with pytest.raises(ValidationError) as search_error:
        service_type.prepare_values(
            {"table_id": table.id, "search_field_ids": [fields[1].id]}, user
        )
    with pytest.raises(ValidationError) as included_error:
        service_type.prepare_values(
            {
                "table_id": table.id,
                "included_field_ids": [data_fixture.create_text_field().id],
            },
            user,
        )
    # The error code lets the editor show the error.
    assert search_error.value.detail["error"] == "invalid_field"
    assert included_error.value.detail["error"] == "invalid_field"

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
        table=table, include_all_fields=False
    )
    service.included_fields.set([fields[1]])

    schema = service.get_type().generate_schema(service)

    assert schema["type"] == "array"
    assert set(schema["items"]["properties"]) == {
        "id",
        "row",
        "score",
        "similarity",
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
def test_paths_of_later_automation_nodes_are_imported(data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    workflow = data_fixture.create_automation_workflow(
        user,
        automation=data_fixture.create_automation_application(
            user=user, workspace=table.database.workspace
        ),
    )
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowSemanticSearchActionNodeType.type,
        service_kwargs={"table": table},
    )
    id_mapping = {
        "automation_workflow_nodes": {node.id: node.id},
        "database_fields": {fields[0].id: 123},
    }

    assert PreviousNodeProviderType().import_path(
        [str(node.id), "0", "row", fields[0].db_column], id_mapping
    ) == [str(node.id), "0", "row", "field_123"]


@pytest.mark.django_db
def test_publishing_keeps_the_chosen_fields(data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    chosen = {
        "table": table,
        "search_query": "'chocolate cake'",
        "search_all_fields": False,
        "include_all_fields": False,
    }
    builder = data_fixture.create_builder_application(
        user=user, workspace=table.database.workspace
    )
    data_source = data_fixture.create_builder_data_source(
        user=user,
        page=data_fixture.create_builder_page(user=user, builder=builder),
        service_model_class=LocalBaserowSemanticSearch,
        integration=data_fixture.create_local_baserow_integration(
            user=user, application=builder
        ),
        **chosen,
    )
    workflow = data_fixture.create_automation_workflow(
        user,
        automation=data_fixture.create_automation_application(
            user=user, workspace=table.database.workspace
        ),
    )
    node = data_fixture.create_automation_node(
        workflow=workflow,
        type=LocalBaserowSemanticSearchActionNodeType.type,
        service_kwargs={
            "integration": data_fixture.create_local_baserow_integration(
                user=user, application=workflow.automation
            ),
            **chosen,
        },
    )
    for service in (data_source.service.specific, node.service.specific):
        service.search_fields.set([fields[0]])
        service.included_fields.set([fields[0], fields[1]])

    # Publishing doesn't import the databases, so the fields stay the same.
    domain = data_fixture.create_builder_custom_domain(builder=builder)
    DomainHandler().publish(domain)
    domain.refresh_from_db()
    published_workflow = AutomationWorkflowHandler().publish(workflow)

    published_services = [
        DataSource.objects.get(page__builder=domain.published_to).service.specific,
        AutomationNode.objects.get(
            workflow=published_workflow,
            content_type__model="localbaserowsemanticsearchactionnode",
        ).service.specific,
    ]
    for service in published_services:
        assert service.search_all_fields is False
        assert service.search_field_ids == [fields[0].id]
        assert service.include_all_fields is False
        assert service.included_field_ids == [fields[0].id, fields[1].id]


@pytest.mark.django_db
def test_export_import_service(data_fixture, enterprise_data_fixture, searchable_table):
    user, token, table, fields, rows = searchable_table
    integration = create_integration(data_fixture, user, table)
    service = enterprise_data_fixture.create_local_baserow_semantic_search_service(
        integration=integration,
        table=table,
        search_all_fields=False,
        include_all_fields=False,
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
    assert new_service.include_all_fields is False


@pytest.mark.django_db(transaction=True)
@pytest.mark.enable_signals(
    "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
    "baserow.contrib.database.search.tasks.update_search_data.delay",
)
def test_closest_meaning_wins_when_all_rows_contain_the_words(
    api_client, data_fixture, semantic_search
):
    user, token = data_fixture.create_user_and_token()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_long_text_field(table=table, name="Notes")
    FieldHandler().update_field(user, field, semantic_search_enabled=True)
    texts = [
        "How to create a field in a table",
        "A field has a type. To create a formula, open the field and create how "
        "the field and the field type work, field by field",
        "Rows are records. How to sort by a field: create a sort on the field, "
        "then the field order applies to the field",
    ]
    for text in texts:
        api_client.post(
            reverse("api:database:rows:list", kwargs={"table_id": table.id}),
            {f"field_{field.id}": text},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
    queryset = table.get_model().objects.all()

    matches = SemanticSearchHandler().search(
        [field], "how to create a field", queryset, limit=3
    )

    # The words are in every row, and repeated more often in the others.
    assert [
        getattr(queryset.get(id=match.row_id), field.db_column) for match in matches
    ] == texts
    assert [match.relevance for match in matches] == sorted(
        (match.relevance for match in matches), reverse=True
    )
    # Also when it isn't among the rows ranked best by their words.
    [match] = SemanticSearchHandler().search(
        [field], "how to create a field", queryset, limit=1
    )
    assert getattr(queryset.get(id=match.row_id), field.db_column) == texts[0]
    # And when only some of the rows that contain the words are ranked, because
    # the words of the rows found by their meaning are always ranked.
    with patch(
        "baserow_enterprise.semantic_search.handler.MAX_FULL_TEXT_RANKED_ROWS", 1
    ):
        bounded_matches = SemanticSearchHandler().search(
            [field], "how to create a field", queryset, limit=3
        )
    assert [match.row_id for match in bounded_matches] == [
        match.row_id for match in matches
    ]


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
