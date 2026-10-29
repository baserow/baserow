from unittest.mock import patch

import pytest
from pydantic_ai import ModelRetry

from baserow.contrib.integrations.local_baserow.service_filters.exceptions import (
    ServiceFilterTargetDoesNotExist,
)
from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterState,
    StateFilter,
)
from baserow_enterprise.assistant.exceptions import ServiceFilterGenerationFailed
from baserow_enterprise.assistant.service_filters import ServiceFilterRequestResult
from baserow_enterprise.assistant.tools.services.tools import (
    list_filterable_data_sources,
    update_service_filters,
)

from .utils import make_test_ctx

RUN_REQUEST = (
    "baserow_enterprise.assistant.tools.services.tools.run_service_filter_request"
)


@pytest.mark.django_db
def test_update_service_filters_passes_the_request_through(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)
    state = FilterState(
        "AND",
        (
            StateFilter(
                id="7",
                field_id=3,
                type="equal",
                value={"formula": "get('page_parameter.id')", "mode": "advanced"},
                group=None,
            ),
        ),
        (),
    )

    with patch(RUN_REQUEST) as run_request:
        run_request.return_value = ServiceFilterRequestResult(
            target_kind="builder_data_source",
            target_id=1,
            target_name="Tasks",
            changed=True,
            summary="Added a filter.",
            state=state,
        )
        result = update_service_filters(
            ctx,
            kind="builder_data_source",
            id=1,
            instructions="Name is the ID page parameter",
            thought="test",
        )

    args, kwargs = run_request.call_args
    tool_context, *request = args
    assert (tool_context.user, tool_context.workspace) == (user, workspace)
    assert request == ["builder_data_source", 1, "Name is the ID page parameter"]
    assert kwargs["model_profile"] is ctx.deps.tool_helpers.model_profile
    assert result == {
        "changed": True,
        "summary": "Added a filter.",
        "filter_type": "AND",
        "groups": [],
        "filters": [
            {
                "id": "7",
                "field_id": 3,
                "type": "equal",
                "value": "get('page_parameter.id')",
                "value_is_formula": True,
                "group": None,
            }
        ],
    }


@pytest.mark.django_db
def test_update_service_filters_reports_errors(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)

    with patch(RUN_REQUEST, side_effect=ServiceFilterTargetDoesNotExist()):
        with pytest.raises(ModelRetry, match="list_filterable_data_sources"):
            update_service_filters(
                ctx, kind="automation_node", id=1, instructions="x", thought="t"
            )

    with patch(RUN_REQUEST, side_effect=ServiceFilterGenerationFailed("no luck")):
        assert update_service_filters(
            ctx, kind="automation_node", id=1, instructions="x", thought="t"
        ) == {"changed": False, "error": "no luck"}


@pytest.mark.django_db
def test_list_filterable_data_sources_stays_in_the_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other_workspace = data_fixture.create_workspace(user=user)
    dashboard = data_fixture.create_dashboard_application(workspace=other_workspace)

    with pytest.raises(ModelRetry):
        list_filterable_data_sources(
            make_test_ctx(user, workspace), application_id=dashboard.id, thought="t"
        )


def test_ui_context_carries_the_selected_element():
    from baserow_enterprise.api.assistant.serializers import (
        AssistantMessageRequestSerializer,
    )
    from baserow_enterprise.assistant.types import UIContext, UserUIContext

    serializer = AssistantMessageRequestSerializer(
        data={
            "content": "only amounts over 50",
            "ui_context": {
                "workspace": {"id": 1, "name": "Workspace"},
                "application": {"id": "3", "name": "Portal"},
                "page": {"id": "7", "name": "Tasks"},
                "element": {"id": 20, "type": "table", "data_source_id": 11},
            },
        }
    )
    assert serializer.is_valid(), serializer.errors

    ui_context = UIContext(
        user=UserUIContext(id=1, name="Dev", email="dev@example.com"),
        **serializer.validated_data["ui_context"],
    )
    assert '"element":{"id":20,"type":"table","data_source_id":11}' in (
        ui_context.format()
    )
