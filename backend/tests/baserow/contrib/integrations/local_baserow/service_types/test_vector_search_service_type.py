from unittest.mock import patch

from django.test import override_settings

import pytest
from rest_framework.exceptions import ValidationError

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchHandler
from baserow.core.pgvector import is_pgvector_enabled
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry
from baserow.test_utils.pytest_conftest import FakeDispatchContext


@pytest.fixture
def setup(data_fixture):
    if not is_pgvector_enabled():
        pytest.skip("pgvector is not installed in the test database")
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    table = data_fixture.create_database_table(user=user)
    name = data_fixture.create_text_field(table=table, name="Name")
    with override_settings(BASEROW_EMBEDDINGS_API_URL="http://embeddings.test"):
        notes = FieldHandler().create_field(
            user, table, "long_text", name="Notes", vector_search_enabled=True
        )
    rows = (
        RowHandler()
        .create_rows(
            user,
            table,
            rows_values=[
                {f"field_{name.id}": "Apple", f"field_{notes.id}": "A fruit"},
                {f"field_{name.id}": "Truck", f"field_{notes.id}": "A vehicle"},
            ],
        )
        .created_rows
    )
    integration = data_fixture.create_local_baserow_integration(
        application=page.builder, user=user
    )
    service_type = service_type_registry.get("local_baserow_vector_search")
    return user, table, name, notes, rows, integration, service_type


@pytest.mark.django_db
def test_vector_search_service_validates_its_fields(setup, data_fixture):
    user, table, name, notes, rows, integration, service_type = setup
    other_table = data_fixture.create_database_table(user=user)
    other_field = data_fixture.create_long_text_field(table=other_table)

    base = {"table_id": table.id, "integration_id": integration.id}
    with pytest.raises(ValidationError):
        service_type.prepare_values({**base, "field_id": other_field.id}, user)
    with pytest.raises(ValidationError):
        # Vector search is off on the name field.
        service_type.prepare_values({**base, "field_id": name.id}, user)
    with pytest.raises(ValidationError):
        service_type.prepare_values(
            {**base, "field_id": notes.id, "included_field_ids": [other_field.id]},
            user,
        )

    values = service_type.prepare_values(
        {
            **base,
            "field_id": notes.id,
            "included_field_ids": [name.id],
            "max_results": 3,
            "search_query": "'fruit'",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    assert service.field_id == notes.id
    assert service.included_field_ids == [name.id]
    assert service_type.export_prepared_values(service)["included_field_ids"] == [
        name.id
    ]

    # Switching tables forgets the field selection.
    new_values = service_type.prepare_values(
        {"table_id": other_table.id}, user, instance=service
    )
    assert new_values["field"] is None
    assert new_values["included_field_ids"] == []


@pytest.mark.django_db
def test_vector_search_service_dispatches_matching_rows(setup):
    user, table, name, notes, rows, integration, service_type = setup
    values = service_type.prepare_values(
        {
            "table_id": table.id,
            "integration_id": integration.id,
            "field_id": notes.id,
            "included_field_ids": [name.id],
            "max_results": 1,
            "search_query": "'fruit'",
        },
        user,
    )
    service = ServiceHandler().create_service(service_type, **values)
    dispatch_context = FakeDispatchContext()

    with patch.object(
        SearchHandler,
        "vector_search",
        return_value=[(rows[0].id, 0.93), (rows[1].id, 0.21)],
    ) as search:
        resolved = service_type.resolve_service_formulas(service, dispatch_context)
        result = service_type.dispatch_transform(
            service_type.dispatch_data(service, resolved, dispatch_context)
        )

    assert search.call_args.args[2] == "fruit"
    assert search.call_args.kwargs["limit"] == 2
    assert result.data == {
        "results": [{"id": rows[0].id, "Name": "Apple", "score": 0.93}],
        "count": 1,
    }


@pytest.mark.django_db
def test_vector_search_service_needs_a_field(setup):
    user, table, name, notes, rows, integration, service_type = setup
    values = service_type.prepare_values(
        {"table_id": table.id, "integration_id": integration.id}, user
    )
    service = ServiceHandler().create_service(service_type, **values)
    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        service_type.resolve_service_formulas(service, FakeDispatchContext())
