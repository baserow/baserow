import json
from collections import defaultdict
from unittest.mock import MagicMock, Mock, patch

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest
from django.shortcuts import reverse

import pytest

from baserow.contrib.builder.data_providers.data_provider_types import (
    CurrentRecordDataProviderType,
    DataSourceContextDataProviderType,
    DataSourceDataProviderType,
    DataSourceHandler,
)
from baserow.contrib.builder.data_providers.data_provider_types import (
    ElementHandler as ElementHandlerToMock,
)
from baserow.contrib.builder.data_providers.data_provider_types import (
    FormDataProviderType,
    PageParameterDataProviderType,
    PreviousActionProviderType,
    UserDataProviderType,
)
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import DataSourceDoesNotExist
from baserow.contrib.builder.elements.exceptions import ElementImproperlyConfigured
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.workflow_actions.models import EventTypes
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.core.formula.exceptions import (
    InvalidFormulaContext,
    InvalidFormulaContextContent,
    InvalidRuntimeFormula,
)
from baserow.core.formula.registries import DataProviderType
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.types import DispatchResult
from baserow.core.user_sources.constants import DEFAULT_USER_ROLE_PREFIX
from baserow.core.user_sources.user_source_user import UserSourceUser
from baserow.core.utils import MirrorDict


def get_dispatch_context(data_fixture, api_request_factory, builder, page, data=None):
    """Helper that returns a dispatch context to be used in tests."""

    user_source = data_fixture.create_user_source_with_first_type(application=builder)
    user_source_user = data_fixture.create_user_source_user(
        user_source=user_source,
    )
    token = user_source_user.get_refresh_token().access_token
    fake_request = api_request_factory.post(
        reverse("api:builder:domains:public_dispatch_all", kwargs={"page_id": page.id}),
        {},
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {token}",
    )
    fake_request.user = user_source_user
    if data is not None:
        fake_request.data = data

    return BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=True
    )


def test_page_parameter_data_provider_get_data_chunk():
    page_parameter_provider = PageParameterDataProviderType()

    fake_request = MagicMock()
    fake_request.data = {"metadata": json.dumps({"page_parameter": {"id": 42}})}

    dispatch_context = BuilderDispatchContext(fake_request, None)

    assert page_parameter_provider.get_data_chunk(dispatch_context, ["id"]) == 42
    assert page_parameter_provider.get_data_chunk(dispatch_context, []) is None
    assert (
        page_parameter_provider.get_data_chunk(dispatch_context, ["id", "test"]) is None
    )
    assert page_parameter_provider.get_data_chunk(dispatch_context, ["test"]) is None


@patch(
    "baserow.contrib.builder.data_providers.data_provider_types.FormDataProviderType.validate_data_chunk"
)
def test_form_data_provider_get_data_chunk(mock_validate):
    form_data_provider = FormDataProviderType()

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps({"form_data": {"1": "hello", "2": ["a", "b"]}})
    }

    dispatch_context = BuilderDispatchContext(fake_request, None)
    mock_validate.side_effect = lambda x, y, z: y

    # A single valued form data
    assert form_data_provider.get_data_chunk(dispatch_context, ["1"]) == "hello"
    # A multiple valued form data
    assert form_data_provider.get_data_chunk(dispatch_context, ["2", "*"]) == ["a", "b"]
    # A multiple valued form data at a specific index
    assert form_data_provider.get_data_chunk(dispatch_context, ["2", "0"]) == "a"
    # Paths longer than 2 are unsupported.
    assert form_data_provider.get_data_chunk(dispatch_context, ["2", "*", "z"]) is None
    # Unknown form data fields are None
    assert form_data_provider.get_data_chunk(dispatch_context, ["3"]) is None
    # Empty paths are None
    assert form_data_provider.get_data_chunk(dispatch_context, []) is None


@patch("baserow.contrib.builder.data_providers.data_provider_types.ElementHandler")
def test_form_data_provider_validate_data_chunk(mock_handler):
    mock_element = Mock()
    mock_element.id = 42
    mock_element_type = Mock()
    mock_element_type.type = "elt_type"

    mock_element.get_type.return_value = mock_element_type
    mock_handler().get_element.return_value = mock_element

    form_data_provider = FormDataProviderType()

    mock_element_type.is_valid.return_value = "something"
    assert form_data_provider.validate_data_chunk("1", "horse", {}) == "something"

    def raise_exc(x, y, z):
        raise ValueError("Error")

    mock_element_type.is_valid.side_effect = raise_exc
    with pytest.raises(InvalidFormulaContextContent) as exc:
        assert form_data_provider.validate_data_chunk("1", 42, {})

    assert exc.value.args[0] == "Error"

    def raise_element_exc(x, y, z):
        raise ElementImproperlyConfigured("Error")

    mock_element_type.is_valid.side_effect = raise_element_exc
    with pytest.raises(InvalidRuntimeFormula) as exc:
        assert form_data_provider.validate_data_chunk("1", 42, {})

    assert (
        exc.value.args[0]
        == "The form element with ID 42 of type elt_type is misconfigured: Error"
    )


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="2",
        name="Item",
    )

    data_source_provider = DataSourceDataProviderType()

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )

    assert (
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, fields[1].db_column]
        )
        == "Orange"
    )


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk_with_list_data_source(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        table=table,
        name="Items",
    )

    data_source_provider = DataSourceDataProviderType()

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )

    assert (
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, "0", fields[1].db_column]
        )
        == "Blue"
    )

    assert (
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, "2", fields[1].db_column]
        )
        == "White"
    )

    assert (
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, "0", "id"]
        )
        == rows[0].id
    )

    assert data_source_provider.get_data_chunk(
        dispatch_context, [data_source.id, "*", fields[1].db_column]
    ) == ["Blue", "Orange", "White", "Green"]


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk_with_formula(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="get('page_parameter.id')",
        name="Item",
    )

    data_source_provider = DataSourceDataProviderType()

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"page_id": page.id},
                "page_parameter": {"id": 2},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    assert (
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, fields[1].db_column]
        )
        == "Orange"
    )


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk_with_formula_using_datasource(
    data_fixture,
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["1"],
            ["2"],
            ["3"],
            ["3"],
        ],
    )
    view2 = data_fixture.create_grid_view(user, table=table2)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view2,
        table=table2,
        row_id="get('page_parameter.id')",
        name="Id source",
    )

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id=f"get('data_source.{data_source2.id}.{fields2[0].db_column}')",
        name="Item",
    )

    data_source_provider = DataSourceDataProviderType()

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"page_id": page.id},
                "page_parameter": {"id": 2},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    assert (
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, fields[1].db_column]
        )
        == "Orange"
    )


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk_with_formula_using_list_datasource(
    data_fixture,
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["1"],
            ["2"],
            ["3"],
            ["3"],
        ],
    )
    view2 = data_fixture.create_grid_view(user, table=table2)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source2 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view2,
        table=table2,
        name="List source",
    )
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id=f"get('data_source.{data_source2.id}.2.{fields2[0].db_column}')",
        name="Item",
    )

    data_source_provider = DataSourceDataProviderType()

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"page_id": page.id},
                "page_parameter": {"id": 2},
            }
        )
    }
    fake_request.GET = {"count": 20}

    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    assert (
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, fields[1].db_column]
        )
        == "White"
    )


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk_with_formula_to_missing_datasource(
    data_fixture,
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["1"],
            ["2"],
            ["3"],
            ["3"],
        ],
    )
    view2 = data_fixture.create_grid_view(user, table=table2)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="get('data_source.99999.Id')",
        name="Item",
    )

    data_source_provider = DataSourceDataProviderType()

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "page_parameter": {},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)

    with pytest.raises(ServiceImproperlyConfiguredDispatchException):
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, fields[1].db_column]
        )


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk_with_formula_recursion(
    data_fixture,
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["1"],
            ["2"],
            ["3"],
            ["3"],
        ],
    )
    view2 = data_fixture.create_grid_view(user, table=table2)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="",
        name="Item",
    )

    data_source.service.row_id = (
        f"get('data_source.{data_source.id}.{fields2[0].db_column}')"
    )
    data_source.service.save()

    data_source_provider = DataSourceDataProviderType()

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "data_source": {"page_id": page.id},
                "page_parameter": {},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, fields[1].db_column]
        )

    assert (
        exc.value.args[0] == 'Error in formula for "row_id": Formula recursion detected'
    )


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk_with_formula_using_another_datasource(
    data_fixture,
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["42"],
            [f"{rows[1].id}"],
            ["44"],
            ["45"],
        ],
    )
    view2 = data_fixture.create_grid_view(user, table=table2)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)

    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view2,
        table=table2,
        row_id=f"'{rows2[1].id}'",
        name="Id source",
    )

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id=f"get('data_source.{data_source2.id}.{fields2[0].db_column}')",
        name="Item",
    )

    data_source_provider = DataSourceDataProviderType()

    dispatch_context = BuilderDispatchContext(
        HttpRequest(), page, only_expose_public_allowed_properties=False
    )

    assert (
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, fields[1].db_column]
        )
        == "Orange"
    )


@pytest.mark.django_db
def test_data_source_data_provider_get_data_chunk_with_formula_using_datasource_calling_each_others(
    data_fixture,
):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
            ("My Color", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
            ["Audi", "Orange"],
            ["Volkswagen", "White"],
            ["Volkswagen", "Green"],
        ],
    )
    view = data_fixture.create_grid_view(user, table=table)
    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Id", "text"),
        ],
        rows=[
            ["1"],
            ["2"],
            ["3"],
            ["3"],
        ],
    )
    view2 = data_fixture.create_grid_view(user, table=table2)
    builder = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        user=user, application=builder
    )
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view,
        table=table,
        row_id="",
        name="Item",
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        integration=integration,
        view=view2,
        table=table2,
        row_id=f"get('data_source.{data_source.id}.id')",
        name="Id source",
    )

    data_source.service.row_id = f"get('data_source.{data_source2.id}.id')"
    data_source.service.save()

    data_source_provider = DataSourceDataProviderType()

    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "page_parameter": {},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    with pytest.raises(ServiceImproperlyConfiguredDispatchException) as exc:
        data_source_provider.get_data_chunk(
            dispatch_context, [data_source.id, fields[1].db_column]
        )

    assert (
        exc.value.args[0]
        == "You can't reference a data source after the current data source"
    )


@pytest.mark.django_db
def test_data_source_formula_import_only_datasource(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        row_id="",
        name="Item",
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        row_id="",
        name="Item",
    )

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["builder_data_sources"] = {data_source.id: data_source2.id}

    result = import_formula(
        BaserowFormulaObject.create(f"get('data_source.{data_source.id}.field_10')"),
        id_mapping,
    )

    assert result["formula"] == f"get('data_source.{data_source2.id}.field_10')"


@pytest.mark.django_db
def test_data_source_formula_import_get_row_datasource_and_field(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        row_id="",
        name="Item",
    )
    data_source2 = data_fixture.create_builder_local_baserow_get_row_data_source(
        row_id="",
        name="Item",
    )
    field_1 = data_fixture.create_text_field(order=1)
    field_2 = data_fixture.create_text_field(order=2)

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["builder_data_sources"] = {data_source.id: data_source2.id}
    id_mapping["database_fields"] = {field_1.id: field_2.id}

    result = import_formula(
        BaserowFormulaObject.create(
            f"get('data_source.{data_source.id}.field_{field_1.id}')"
        ),
        id_mapping,
    )

    assert (
        result["formula"] == f"get('data_source.{data_source2.id}.field_{field_2.id}')"
    )


@pytest.mark.django_db
def test_data_source_formula_import_list_row_datasource_and_field(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        name="Item",
    )
    data_source2 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        name="Item",
    )
    field_1 = data_fixture.create_text_field(order=1)
    field_2 = data_fixture.create_text_field(order=2)

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["builder_data_sources"] = {data_source.id: data_source2.id}
    id_mapping["database_fields"] = {field_1.id: field_2.id}

    result = import_formula(
        BaserowFormulaObject.create(
            f"get('data_source.{data_source.id}.10.field_{field_1.id}')"
        ),
        id_mapping,
    )

    assert (
        result["formula"]
        == f"get('data_source.{data_source2.id}.10.field_{field_2.id}')"
    )


@pytest.mark.django_db
def test_data_source_formula_import_missing_get_row_datasource(data_fixture):
    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["builder_data_sources"] = {}

    result = import_formula(
        BaserowFormulaObject.create("get('data_source.42.field_24')"), id_mapping
    )

    assert result["formula"] == f"get('data_source.42.field_24')"

    id_mapping["builder_data_sources"] = {42: 42}

    result = import_formula(
        BaserowFormulaObject.create("get('data_source.42.field_24')"), id_mapping
    )

    assert result["formula"] == "get('data_source.42.field_24')"


@pytest.mark.django_db
def test_data_source_context_data_provider_get_data_chunk(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user, columns=[("Name", "text")], rows=[]
    )
    field_handler = FieldHandler()
    field = field_handler.create_field(
        user=user,
        table=table,
        type_name="single_select",
        name="Category",
        select_options=[
            {
                "value": "Bakery",
                "color": "red",
            },
            {
                "value": "Grocery",
                "color": "green",
            },
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        table=table,
        row_id="",
        name="Item",
    )
    data_source_context_provider = DataSourceContextDataProviderType()

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "page_parameter": {},
            }
        )
    }
    dispatch_context = BuilderDispatchContext(
        fake_request, page, only_expose_public_allowed_properties=False
    )

    # For fields that are not single select, `get_data_chunk` returns an empty response
    assert (
        data_source_context_provider.get_data_chunk(
            dispatch_context, [str(data_source.id), fields[0].db_column]
        )
        is None
    )

    # For single select fields, we should be able to select one/all of the options
    assert (
        data_source_context_provider.get_data_chunk(
            dispatch_context, [str(data_source.id), field.db_column, "0", "value"]
        )
        == "Bakery"
    )

    assert data_source_context_provider.get_data_chunk(
        dispatch_context, [str(data_source.id), field.db_column, "*", "value"]
    ) == ["Bakery", "Grocery"]

    assert data_source_context_provider.get_data_chunk(
        dispatch_context, [str(data_source.id), field.db_column, "*", "color"]
    ) == ["red", "green"]


@pytest.mark.django_db
def test_data_source_data_context_data_provider_import_path(data_fixture):
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source()
    data_source_context_provider = DataSourceContextDataProviderType()

    assert data_source_context_provider.import_path(["1"], {}) == ["1"]
    assert data_source_context_provider.import_path(
        ["1"], {"builder_data_sources": {1: 2}}
    ) == ["2"]

    assert data_source_context_provider.import_path(
        ["1"], {"builder_data_sources": {1: data_source.id}}
    ) == [str(data_source.id)]


@pytest.mark.django_db
def test_table_element_formula_migration_with_current_row_provider(data_fixture):
    user = data_fixture.create_user()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
        ],
    )

    table2, fields2, rows2 = data_fixture.build_table(
        user=user,
        columns=[
            ("Name", "text"),
        ],
        rows=[
            ["BMW", "Blue"],
        ],
    )

    page = data_fixture.create_builder_page(user=user)

    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        page=page,
        table=table,
    )

    data_source2 = data_fixture.create_builder_local_baserow_list_rows_data_source(
        table=table2,
    )

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["builder_data_sources"] = {data_source.id: data_source2.id}
    id_mapping["database_fields"] = {fields[0].id: fields2[0].id}

    result = import_formula(
        BaserowFormulaObject.create(f"get('current_record.field_{fields[0].id}')"),
        id_mapping,
        data_source_id=data_source2.id,
    )

    assert result["formula"] == f"get('current_record.field_{fields2[0].id}')"


@pytest.mark.django_db
def test_form_data_provider_type_import_path(data_fixture):
    element = data_fixture.create_builder_heading_element()
    element_duplicated = ElementHandler().duplicate_element(element)["elements"][0]

    id_mapping = {"builder_page_elements": {element.id: element_duplicated.id}}
    path = [str(element.id), "test"]

    path_imported = FormDataProviderType().import_path(path, id_mapping)

    assert path_imported == [str(element_duplicated.id), "test"]


@pytest.mark.django_db
def test_previous_action_data_provider_get_data_chunk(data_fixture):
    previous_action_data_provider = PreviousActionProviderType()

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    button_element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_notification_workflow_action(
        element=button_element, page=page
    )

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps(
            {"previous_action": {str(workflow_action.id): {"path": {"to": 100}}}}
        )
    }
    dispatch_context = BuilderDispatchContext(fake_request, None)

    with pytest.raises(InvalidFormulaContext):
        previous_action_data_provider.get_data_chunk(
            dispatch_context, [str(workflow_action.id), "path", "to"]
        )

    fake_request.data = {
        "metadata": json.dumps(
            {
                "previous_action": {
                    "current_dispatch_id": "something",
                    str(workflow_action.id): {"path": {"to": 100}},
                }
            }
        )
    }
    dispatch_context = BuilderDispatchContext(fake_request, None)

    assert (
        previous_action_data_provider.get_data_chunk(
            dispatch_context, [str(workflow_action.id), "path", "to"]
        )
        == 100
    )

    with pytest.raises(InvalidFormulaContext):
        previous_action_data_provider.get_data_chunk(dispatch_context, ["invalid"])


@pytest.mark.django_db
def test_previous_action_data_provider_get_data_chunk_returns_cached_result(
    data_fixture,
):
    """
    Ensure that when a current_dispatch_id is present in the request and it matches
    a previously cached result, that result is returned.
    """

    previous_action_data_provider = PreviousActionProviderType()

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    button_element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        element=button_element, page=page
    )

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "previous_action": {
                    "current_dispatch_id": "abc123",
                    str(workflow_action.id): {},
                }
            }
        )
    }
    dispatch_context = BuilderDispatchContext(fake_request, None)

    previous_action_data_provider.get_dispatch_action_cache_key = MagicMock(
        return_value="bar"
    )

    with patch(
        "baserow.contrib.builder.data_providers.data_provider_types.cache"
    ) as mock_cache:
        mock_cache.get.return_value = {"id": "mock-cached-data"}
        result = previous_action_data_provider.get_data_chunk(
            dispatch_context, [str(workflow_action.id), "id"]
        )

    assert result == "mock-cached-data"


def test_previous_action_data_provider_post_dispatch_caches_result():
    """
    Ensure that when a current_dispatch_id is present in the request, the
    provided result is cached.
    """

    previous_action_data_provider = PreviousActionProviderType()

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "previous_action": {
                    "current_dispatch_id": "foo-bar-123",
                }
            }
        )
    }
    dispatch_context = BuilderDispatchContext(fake_request, None)

    workflow_action = MagicMock()
    workflow_action.id = 100

    mock_cache_key = "mock-cache-key"
    mock_result = DispatchResult(data={"mock-key": "mock-value"})
    previous_action_data_provider.get_dispatch_action_cache_key = MagicMock(
        return_value=mock_cache_key
    )

    with patch(
        "baserow.contrib.builder.data_providers.data_provider_types.cache"
    ) as mock_cache:
        previous_action_data_provider.post_dispatch(
            dispatch_context, workflow_action, mock_result
        )

    previous_action_data_provider.get_dispatch_action_cache_key.assert_called_once_with(
        "foo-bar-123", 100
    )
    mock_cache.set.assert_called_once_with(
        mock_cache_key,
        mock_result.data,
        timeout=settings.BUILDER_DISPATCH_ACTION_CACHE_TTL_SECONDS,
    )


def test_previous_action_data_provider_post_dispatch_with_empty_response_cache_result():
    """
    Ensure that when a current_dispatch_id is present in the request, the
    provided result is cached.
    """

    previous_action_data_provider = PreviousActionProviderType()

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "previous_action": {
                    "current_dispatch_id": "foo-bar-123",
                }
            }
        )
    }
    dispatch_context = BuilderDispatchContext(fake_request, None)

    workflow_action = MagicMock()
    workflow_action.id = 100

    mock_cache_key = "mock-cache-key"
    mock_result = DispatchResult(status=204)
    previous_action_data_provider.get_dispatch_action_cache_key = MagicMock(
        return_value=mock_cache_key
    )

    with patch(
        "baserow.contrib.builder.data_providers.data_provider_types.cache"
    ) as mock_cache:
        previous_action_data_provider.post_dispatch(
            dispatch_context, workflow_action, mock_result
        )

    mock_cache.set.assert_called_once_with(
        mock_cache_key,
        {},
        timeout=settings.BUILDER_DISPATCH_ACTION_CACHE_TTL_SECONDS,
    )


@pytest.mark.parametrize(
    "dispatch_id,action_id,expected_cache_key",
    [
        (1, 2, "builder_dispatch_action_1_2"),
        (123, 456, "builder_dispatch_action_123_456"),
        ("234", "567", "builder_dispatch_action_234_567"),
    ],
)
def test_get_dispatch_action_cache_key(dispatch_id, action_id, expected_cache_key):
    """
    Test the get_dispatch_action_cache_key() method. Ensure that the expected
    key is returned.
    """

    previous_action_data_provider = PreviousActionProviderType()

    cache_key = previous_action_data_provider.get_dispatch_action_cache_key(
        dispatch_id, action_id
    )

    assert cache_key == expected_cache_key


@pytest.mark.django_db
def test_previous_action_data_provider_import_path():
    previous_action_data_provider = PreviousActionProviderType()
    path = ["1", "field"]

    valid_id_mapping = {"builder_workflow_actions": {1: 2}}
    invalid_id_mapping = {"builder_workflow_actions": {0: 1}}

    assert previous_action_data_provider.import_path(path, {}) == ["1", "field"]
    assert previous_action_data_provider.import_path(path, invalid_id_mapping) == [
        "1",
        "field",
    ]
    assert previous_action_data_provider.import_path(path, valid_id_mapping) == [
        "2",
        "field",
    ]


@pytest.mark.django_db
def test_user_data_provider_get_data_chunk(data_fixture):
    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)

    user_data_provider_type = UserDataProviderType()

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "page_parameter": {},
            }
        )
    }
    fake_request.user_source_user = AnonymousUser()

    dispatch_context = BuilderDispatchContext(fake_request, page)

    assert not user_data_provider_type.get_data_chunk(
        dispatch_context, ["is_authenticated"]
    )

    assert user_data_provider_type.get_data_chunk(dispatch_context, ["id"]) == 0

    fake_request.user_source_user = UserSourceUser(
        None, None, 42, "username", "e@ma.il", "foo_role"
    )

    assert user_data_provider_type.get_data_chunk(
        dispatch_context, ["is_authenticated"]
    )
    assert (
        user_data_provider_type.get_data_chunk(dispatch_context, ["email"]) == "e@ma.il"
    )
    assert user_data_provider_type.get_data_chunk(dispatch_context, ["id"]) == 42
    assert (
        user_data_provider_type.get_data_chunk(dispatch_context, ["role"]) == "foo_role"
    )


@pytest.mark.django_db
def test_translate_default_user_role_returns_same_role(data_fixture):
    """
    Ensure the UserDataProviderType's get_data_chunk() method returns
    the same User Role.

    When the role is a non-Default User Role, the same role should be returned.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    user_data_provider_type = UserDataProviderType()

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "page_parameter": {},
            }
        )
    }
    fake_request.user_source_user = AnonymousUser()

    dispatch_context = BuilderDispatchContext(fake_request, page)

    user_role = "foo_role"
    fake_request.user_source_user = UserSourceUser(
        None, None, 42, "username", "e@ma.il", user_role
    )

    assert (
        user_data_provider_type.get_data_chunk(dispatch_context, ["role"]) == user_role
    )


@pytest.mark.django_db
def test_translate_default_user_role_returns_translated_role(data_fixture):
    """
    Ensure the UserDataProviderType's get_data_chunk() method returns
    the translated Default User Role.
    """

    user = data_fixture.create_user()
    page = data_fixture.create_builder_page(user=user)
    user_source_name = "FooUserSource"
    user_source = data_fixture.create_user_source_with_first_type(name=user_source_name)
    default_user_source_name = f"{DEFAULT_USER_ROLE_PREFIX}{user_source.id}"

    user_data_provider_type = UserDataProviderType()

    fake_request = MagicMock()
    fake_request.data = {
        "metadata": json.dumps(
            {
                "page_parameter": {},
            }
        )
    }

    dispatch_context = BuilderDispatchContext(fake_request, page)
    fake_request.user_source_user = UserSourceUser(
        user_source, None, 42, "username", "e@ma.il", default_user_source_name
    )

    assert (
        user_data_provider_type.get_data_chunk(dispatch_context, ["role"])
        == f"{user_source_name} member"
    )


@pytest.mark.django_db
def test_current_record_provider_get_data_chunk_without_record_index(data_fixture):
    current_record_provider = CurrentRecordDataProviderType()

    user, token = data_fixture.create_user_and_token()

    fake_request = HttpRequest()
    fake_request.data = {"metadata": json.dumps({})}

    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, event=EventTypes.CLICK, user=user
    )

    dispatch_context = BuilderDispatchContext(fake_request, page, workflow_action)
    assert current_record_provider.get_data_chunk(dispatch_context, ["path"]) is None


def test_current_record_provider_get_data_chunk_for_idx():
    current_record_provider = CurrentRecordDataProviderType()
    fake_request = HttpRequest()
    fake_request.data = {
        "metadata": json.dumps({"current_record": {"index": 123, "record_id": 123}})
    }
    dispatch_context = BuilderDispatchContext(fake_request, None)
    assert current_record_provider.get_data_chunk(dispatch_context, ["__idx__"]) == 123


@pytest.mark.django_db
def test_current_record_provider_get_data_chunk(data_fixture):
    user, token = data_fixture.create_user_and_token()

    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Animal", "text"),
        ],
        rows=[
            ["Badger"],
            ["Horse"],
            ["Bison"],
        ],
    )
    field = table.field_set.get(name="Animal")
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, table=table, integration_args={"authorized_user": user}
    )
    repeat_element = data_fixture.create_builder_repeat_element(
        page=page, data_source=data_source
    )
    button_element = data_fixture.create_builder_button_element(
        page=page, parent_element=repeat_element
    )

    workflow_action = data_fixture.create_local_baserow_create_row_workflow_action(
        page=page, element=button_element, event=EventTypes.CLICK, user=user
    )

    fake_request = HttpRequest()
    fake_request.user = user
    fake_request.data = {
        "metadata": json.dumps(
            {"current_record": {"index": 0, "record_id": rows[0].id}}
        )
    }

    dispatch_context = BuilderDispatchContext(
        fake_request, page, workflow_action, only_expose_public_allowed_properties=False
    )

    current_record_provider = CurrentRecordDataProviderType()

    assert (
        current_record_provider.get_data_chunk(dispatch_context, [field.db_column])
        == "Badger"
    )


@pytest.mark.django_db
def test_current_record_provider_type_import_path(data_fixture):
    # When a `current_record` provider is imported, and the path only contains the
    # current record index (`__idx__`), then there is no need to update the path.
    id_mapping = {"builder_page_elements": {}}
    assert CurrentRecordDataProviderType().import_path(["__idx__"], id_mapping) == [
        "__idx__"
    ]

    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source()
    field_1 = data_fixture.create_text_field(order=1)
    field_2 = data_fixture.create_text_field(order=2)

    id_mapping = defaultdict(lambda: MirrorDict())
    id_mapping["database_fields"] = {field_1.id: field_2.id}

    assert CurrentRecordDataProviderType().import_path(
        [field_1.db_column], id_mapping, data_source_id=data_source.id
    ) == [field_2.db_column]


def test_extract_properties_base_implementation():
    """Test that the base implementation of extract_properties() returns None."""

    for provider_type in [
        DataSourceDataProviderType,
        FormDataProviderType,
        PageParameterDataProviderType,
        PreviousActionProviderType,
        UserDataProviderType,
    ]:
        assert provider_type().extract_properties([]) == {}


@pytest.mark.parametrize("path", ([], [""], ["foo"]))
@pytest.mark.django_db
def test_data_source_data_extract_properties_returns_none_if_invalid_data_source_id(
    path,
):
    """
    Test the DataSourceDataProviderType::extract_properties() method.

    Ensure that None is returned if the data_source_id cannot be inferred or
    is invalid.
    """

    result = DataSourceDataProviderType().extract_properties(path)
    assert result == {}


@patch.object(DataSourceHandler, "get_data_source")
@pytest.mark.django_db
def test_data_source_data_extract_properties_calls_correct_service_type(
    mocked_get_data_source,
):
    """
    Test the DataSourceDataProviderType::extract_properties() method.

    Ensure that the correct service type is called.
    """

    expected = "123"

    mocked_service_type = MagicMock()
    mocked_service_type.returns_list = False
    mocked_service_type.extract_properties.return_value = expected
    mocked_data_source = MagicMock()
    mocked_data_source.service.specific.get_type = MagicMock(
        return_value=mocked_service_type
    )
    mocked_get_data_source.return_value = mocked_data_source

    data_source_id = "1"
    path = [data_source_id, expected]
    result = DataSourceDataProviderType().extract_properties(path)

    assert result == {mocked_data_source.service_id: expected}
    mocked_get_data_source.assert_called_once_with(int(data_source_id), with_cache=True)
    mocked_service_type.extract_properties.assert_called_once_with([expected])

    mocked_service_type.returns_list = True
    mocked_service_type.extract_properties.reset_mock()

    result = DataSourceDataProviderType().extract_properties(
        [data_source_id, "1", expected]
    )
    mocked_service_type.extract_properties.assert_called_once_with([expected])
    assert result == {mocked_data_source.service_id: expected}


@pytest.mark.django_db
def test_data_source_data_extract_properties_returns_expected_results(data_fixture):
    """
    Test the DataSourceDataProviderType::extract_properties() method. Ensure that
    the expected Field name is returned.
    """

    user, _ = data_fixture.create_user_and_token()
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Drink", "text"),
            ("Dessert", "text"),
        ],
        rows=[
            ["Paneer Tikka", "Lassi", "Rasmalai"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        table=table,
        row_id="1",
    )

    data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Solids",
                "type": "text",
                "config": {
                    "value": f"get('data_source.{data_source.id}.field_{fields[0].id}')"
                },
            },
        ],
    )

    path = [data_source.id, f"field_{fields[0].id}"]

    result = DataSourceDataProviderType().extract_properties(path)

    expected = {data_source.service_id: [f"field_{fields[0].id}"]}
    assert result == expected


@pytest.mark.parametrize("path", ([], [""], ["foo"]))
@pytest.mark.django_db
def test_data_source_context_extract_properties_returns_none_if_invalid_data_source_id(
    path,
):
    """
    Test the DataSourceContextDataProviderType::extract_properties() method.

    Ensure that {} is returned if the data_source_id cannot be inferred or
    is invalid.
    """

    result = DataSourceContextDataProviderType().extract_properties(path)
    assert result == {}


@patch.object(DataSourceHandler, "get_data_source")
@pytest.mark.django_db
def test_data_source_context_extract_properties_calls_correct_service_type(
    mocked_get_data_source,
):
    """
    Test the DataSourceContextDataProviderType::extract_properties() method.

    Ensure that the correct service type is called.
    """

    expected = "123"

    mocked_service_type = MagicMock()
    mocked_service_type.returns_list = False
    mocked_service_type.extract_properties.return_value = expected
    mocked_data_source = MagicMock()
    mocked_data_source.service.specific.get_type = MagicMock(
        return_value=mocked_service_type
    )
    mocked_get_data_source.return_value = mocked_data_source

    data_source_id = "1"
    path = [data_source_id, expected]
    result = DataSourceContextDataProviderType().extract_properties(path)

    assert result == {mocked_data_source.service_id: expected}
    mocked_get_data_source.assert_called_once_with(int(data_source_id), with_cache=True)
    mocked_service_type.extract_properties.assert_called_once_with([expected])

    mocked_service_type.returns_list = True
    mocked_service_type.extract_properties.reset_mock()
    mocked_service_type.reset_mock()

    result = DataSourceContextDataProviderType().extract_properties(
        [data_source_id, expected]
    )

    mocked_service_type.extract_properties.assert_called_once_with([expected])
    assert result == {mocked_data_source.service_id: expected}


@pytest.mark.django_db
def test_data_source_context_extract_properties_returns_expected_results(data_fixture):
    """
    Test the DataSourceContextDataProviderType::extract_properties() method. Ensure that
    the expected Field name is returned.
    """

    user, _ = data_fixture.create_user_and_token()
    table, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Drink", "text"),
            ("Dessert", "text"),
        ],
        rows=[
            ["Paneer Tikka", "Lassi", "Rasmalai"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_get_row_data_source(
        user=user,
        page=page,
        table=table,
        row_id="1",
    )

    data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Solids",
                "type": "text",
                "config": {
                    "value": f"get('data_source.{data_source.id}.field_{fields[0].id}')"
                },
            },
        ],
    )

    path = [str(data_source.id), f"field_{fields[0].id}"]

    result = DataSourceContextDataProviderType().extract_properties(path)

    expected = {data_source.service_id: [f"field_{fields[0].id}"]}
    assert result == expected


@pytest.mark.parametrize(
    "path",
    (
        ["10", 999],
        [20, 888],
    ),
)
@pytest.mark.django_db
@patch.object(DataSourceHandler, "get_data_source")
def test_data_source_context_data_provider_extract_properties_raises_if_data_source_doesnt_exist(
    mock_get_data_source,
    path,
):
    """
    Test the DataSourceContextDataProviderType::extract_properties() method.

    Ensure that InvalidRuntimeFormula is raised if the Data Source doesn't exist.
    """

    mock_get_data_source.side_effect = DataSourceDoesNotExist()

    with pytest.raises(InvalidRuntimeFormula):
        DataSourceContextDataProviderType().extract_properties(path)

    mock_get_data_source.assert_called_once_with(int(path[0]), with_cache=True)


@pytest.mark.parametrize(
    "path",
    (
        ["10", 999],
        [20, 888],
    ),
)
@pytest.mark.django_db
@patch.object(DataSourceHandler, "get_data_source")
def test_data_source_data_provider_extract_properties_raises_if_data_source_doesnt_exist(
    mock_get_data_source,
    path,
):
    """
    Test the DataSourceDataProviderType::extract_properties() method.

    Ensure that InvalidRuntimeFormula is raised if the Data Source doesn't exist.
    """

    mock_get_data_source.side_effect = DataSourceDoesNotExist()

    with pytest.raises(InvalidRuntimeFormula):
        DataSourceDataProviderType().extract_properties(path)

    mock_get_data_source.assert_called_once_with(int(path[0]), with_cache=True)


@pytest.mark.parametrize("path", ([], [""], ["foo"]))
@pytest.mark.django_db
def test_current_record_extract_properties_returns_none_if_data_source_id_missing(path):
    """
    Test the CurrentRecordDataProviderType::extract_properties() method.

    Ensure that None is returned if the data_source_id is misssing in the
    import context.
    """

    result = CurrentRecordDataProviderType().extract_properties(path)
    assert result == {}


@pytest.mark.parametrize(
    "path,invalid_data_source_id",
    (
        ["10", 999],
        [20, 888],
    ),
)
@pytest.mark.django_db
@patch.object(DataSourceHandler, "get_data_source")
def test_current_record_extract_properties_raises_if_data_source_doesnt_exist(
    mock_get_data_source,
    path,
    invalid_data_source_id,
):
    """
    Test the CurrentRecordDataProviderType::extract_properties() method.

    Ensure that InvalidRuntimeFormula is raised if the Data Source doesn't exist.
    """

    mock_get_data_source.side_effect = DataSourceDoesNotExist()

    with pytest.raises(InvalidRuntimeFormula):
        CurrentRecordDataProviderType().extract_properties(path, invalid_data_source_id)

    mock_get_data_source.assert_called_once_with(
        invalid_data_source_id, with_cache=True
    )


@pytest.mark.django_db
@patch.object(ElementHandlerToMock, "get_import_context_addition")
@patch.object(DataSourceHandler, "get_data_source")
def test_current_record_extract_properties_calls_correct_service_type(
    mock_get_data_source,
    mock_get_import_context_addition,
):
    """
    Test the CurrentRecordDataProviderType::extract_properties() method.

    Ensure that the correct service type is called.
    """

    fake_data_source_id = 100
    mock_get_import_context_addition.return_value = {
        "data_source_id": fake_data_source_id
    }

    expected_field = "field_123"
    mocked_service_type = MagicMock()
    mocked_service_type.returns_list = True
    mocked_service_type.extract_properties.return_value = expected_field

    mocked_data_source = MagicMock()
    mocked_data_source.service_id = 42
    mocked_data_source.service.specific.get_type = MagicMock(
        return_value=mocked_service_type
    )
    mock_get_data_source.return_value = mocked_data_source

    fake_element_id = 10
    path = [expected_field]

    result = CurrentRecordDataProviderType().extract_properties(path, fake_element_id)

    assert result == {mocked_data_source.service_id: expected_field}
    mock_get_data_source.assert_called_once_with(fake_element_id, with_cache=True)
    mocked_service_type.extract_properties.assert_called_once_with([expected_field])


@pytest.mark.django_db
@pytest.mark.parametrize(
    "returns_list,schema_property",
    [
        (
            True,
            "field_123",
        ),
        (
            True,
            None,
        ),
        (
            False,
            "field_123",
        ),
        (
            False,
            None,
        ),
    ],
)
@patch.object(DataSourceHandler, "get_data_source")
def test_current_record_extract_properties_called_with_correct_path(
    mock_get_data_source, returns_list, schema_property
):
    """
    Test the CurrentRecordDataProviderType::extract_properties() method.

    Ensure that the `path` is generated correctly and passed to the service type.
    """

    service_id = 100
    data_source_id = 50

    mock_service_type = MagicMock()
    mock_service_type.returns_list = returns_list
    mock_service_type.extract_properties.return_value = ["field_999"]

    mock_data_source = MagicMock()
    mock_data_source.service_id = service_id
    mock_data_source.service.specific.get_type.return_value = mock_service_type

    mock_get_data_source.return_value = mock_data_source

    path = ["*"]

    result = CurrentRecordDataProviderType().extract_properties(
        path,
        data_source_id,
        schema_property,
    )

    mock_get_data_source.assert_called_once_with(data_source_id, with_cache=True)

    if returns_list:
        if schema_property:
            mock_service_type.extract_properties.assert_called_once_with(
                [schema_property, *path]
            )
        else:
            mock_service_type.extract_properties.assert_called_once_with(path)
        assert result == {service_id: ["field_999"]}
    else:
        if schema_property:
            mock_service_type.extract_properties.assert_called_once_with(
                [schema_property, *path]
            )
            assert result == {service_id: ["field_999"]}
        else:
            # If service type doesn't return a list (e.g. Get Row) and
            # there is no schema_property, ensure we return early with an
            # empty dict, since there are no fields to extract.
            mock_service_type.extract_properties.assert_not_called()
            assert result == {}


@pytest.mark.django_db
@patch.object(DataSourceHandler, "get_data_source")
def test_current_record_extract_properties_returns_empty_if_invalid_data_source_id(
    mock_get_data_source,
):
    """
    Test the CurrentRecordDataProviderType::extract_properties() method. Ensure that
    an empty dict is returned if the Data Source ID is invalid.
    """

    invalid_data_source_id = None
    path = ["field_123"]

    result = CurrentRecordDataProviderType().extract_properties(
        path, invalid_data_source_id
    )

    assert result == {}
    mock_get_data_source.assert_not_called()


@pytest.mark.django_db
def test_current_record_extract_properties_returns_expected_results(data_fixture):
    """
    Test the CurrentRecordDataProviderType::extract_properties() method. Ensure that
    the expected Field name is returned.
    """

    user, _ = data_fixture.create_user_and_token()
    table, fields, rows = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Drink", "text"),
            ("Dessert", "text"),
        ],
        rows=[
            ["Paneer Tikka", "Lassi", "Rasmalai"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        user=user,
        page=page,
        table=table,
    )

    data_fixture.create_builder_table_element(
        page=page,
        data_source=data_source,
        fields=[
            {
                "name": "Solids",
                "type": "text",
                "config": {"value": f"get('current_record.field_{fields[0].id}')"},
            },
        ],
    )

    path = [f"field_{fields[0].id}"]

    result = CurrentRecordDataProviderType().extract_properties(path, data_source.id)

    expected = {data_source.service_id: [f"field_{fields[0].id}"]}
    assert result == expected


def test_data_provider_type_extract_properties_base_method():
    """Test the DataProviderType::extract_properties() base method."""

    class FakeDataProviderType(DataProviderType):
        type = "fake_data_provider_type"

        def get_data_chunk(self, *args, **kwargs):
            return None

    result = FakeDataProviderType().extract_properties([])

    assert result == {}


@pytest.mark.parametrize(
    "path",
    (
        [],
        [""],
        ["foo"],
        ["foo", "bar", "baz"],
    ),
)
@pytest.mark.django_db
def test_previous_action_extract_properties_returns_empty_if_invalid_path_parts(
    path,
):
    """
    Test the PreviousActionProviderType::extract_properties() method.

    Ensure that an empty dict is returned if the path list doesn't have exactly
    2 elements.
    """

    result = PreviousActionProviderType().extract_properties(path)
    assert result == {}


@pytest.mark.django_db
def test_previous_action_extract_properties_raises_if_invalid_service_id():
    """
    Test the PreviousActionProviderType::extract_properties() method.

    Ensure an exception is raised if the Workflow Action ID is invalid.
    """

    # The service ID of 100 doesn't exist
    with pytest.raises(InvalidRuntimeFormula):
        PreviousActionProviderType().extract_properties(["100", "field_123"])


@pytest.mark.django_db
def test_previous_action_extract_properties_returns_service_id_and_field_id(
    data_fixture,
):
    """
    Test the PreviousActionProviderType::extract_properties() method.

    Ensure an exception is raised if the Workflow Action ID is invalid.
    """

    user = data_fixture.create_user()
    _, fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Fruit", "text"),
            ("Color", "text"),
            ("Country", "text"),
        ],
        rows=[
            ["Apple", "Green", "China"],
            ["Banana", "Yellow", "Ecuador"],
            ["Cherry", "Red", "Turkey"],
        ],
    )
    builder = data_fixture.create_builder_application(user=user)
    page = data_fixture.create_builder_page(user=user, builder=builder)
    button_element = data_fixture.create_builder_button_element(page=page)
    workflow_action = data_fixture.create_local_baserow_update_row_workflow_action(
        element=button_element, page=page
    )
    path = [f"{workflow_action.id}", f"field_{fields[0].id}"]

    properties = PreviousActionProviderType().extract_properties(path)

    assert properties == {workflow_action.service.id: [f"field_{fields[0].id}"]}
