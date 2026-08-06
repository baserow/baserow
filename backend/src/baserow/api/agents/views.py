from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.agents.errors import (
    ERROR_AGENT_DOES_NOT_EXIST,
    ERROR_AGENT_ROLE_DOES_NOT_EXIST,
)
from baserow.api.agents.serializers import (
    AgentListParamsSerializer,
    AgentRequestSerializer,
    AgentSerializer,
    UpdateAgentRequestSerializer,
)
from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.errors import (
    ERROR_GROUP_DOES_NOT_EXIST,
    ERROR_INVALID_SORT_ATTRIBUTE,
    ERROR_INVALID_SORT_DIRECTION,
)
from baserow.api.exceptions import (
    InvalidSortAttributeException,
    InvalidSortDirectionException,
)
from baserow.api.mixins import SearchableViewMixin, SortableViewMixin
from baserow.api.pagination import PageNumberPagination
from baserow.core.agents.exceptions import AgentDoesNotExist, AgentRoleDoesNotExist
from baserow.core.agents.handler import AgentHandler
from baserow.core.agents.service import AgentService
from baserow.core.exceptions import WorkspaceDoesNotExist
from baserow.core.feature_flags import FF_AGENTS, feature_flag_is_enabled
from baserow.core.handler import CoreHandler


class WorkspaceAgentsView(APIView, SearchableViewMixin, SortableViewMixin):
    """Lists agents in a workspace and creates new workspace agents."""

    permission_classes = (IsAuthenticated,)
    search_fields = ["name"]
    sort_field_mapping = {
        "name": "name",
        "role_uid": "role_uid",
        "last_active": "last_active",
        "created_on": "created_on",
    }

    @extend_schema(
        tags=["Agents"],
        description="Lists the agents in a workspace.",
        responses={200: AgentSerializer(many=True)},
    )
    @validate_query_parameters(AgentListParamsSerializer)
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            InvalidSortAttributeException: ERROR_INVALID_SORT_ATTRIBUTE,
            InvalidSortDirectionException: ERROR_INVALID_SORT_DIRECTION,
        }
    )
    def get(self, request, workspace_id, query_params):
        """Returns a paginated, searchable, and sortable list of workspace agents."""

        workspace = CoreHandler().get_workspace(workspace_id)
        queryset = AgentService().list_agents(request.user, workspace)
        queryset = self.apply_search(query_params.get("search"), queryset)
        queryset = self.apply_sorts_or_default_sort(query_params.get("sorts"), queryset)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        return paginator.get_paginated_response(AgentSerializer(page, many=True).data)

    @extend_schema(
        tags=["Agents"],
        description="Creates a new agent in a workspace.",
        request=AgentRequestSerializer,
        responses={200: AgentSerializer},
    )
    @transaction.atomic
    @validate_body(AgentRequestSerializer)
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            AgentRoleDoesNotExist: ERROR_AGENT_ROLE_DOES_NOT_EXIST,
        }
    )
    def post(self, request, data, workspace_id):
        """Creates a new agent in the workspace."""

        feature_flag_is_enabled(FF_AGENTS, raise_if_disabled=True)
        workspace = CoreHandler().get_workspace(workspace_id)
        agent = AgentService().create_agent(request.user, workspace, **data)
        return Response(AgentSerializer(agent).data)


class AgentView(APIView):
    """Updates and deletes an individual agent."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Agents"],
        description="Updates an existing agent.",
        request=UpdateAgentRequestSerializer,
        responses={200: AgentSerializer},
    )
    @transaction.atomic
    @validate_body(UpdateAgentRequestSerializer)
    @map_exceptions(
        {
            AgentDoesNotExist: ERROR_AGENT_DOES_NOT_EXIST,
            AgentRoleDoesNotExist: ERROR_AGENT_ROLE_DOES_NOT_EXIST,
        }
    )
    def patch(self, request, data, agent_id):
        """Updates an existing agent."""

        agent = AgentHandler().get_agent(agent_id)
        agent = AgentService().update_agent(request.user, agent, **data)
        return Response(AgentSerializer(agent).data)

    @extend_schema(
        tags=["Agents"],
        description="Deletes an existing agent.",
        responses={204: None},
    )
    @transaction.atomic
    @map_exceptions({AgentDoesNotExist: ERROR_AGENT_DOES_NOT_EXIST})
    def delete(self, request, agent_id):
        """Deletes an existing agent."""

        agent = AgentHandler().get_agent(agent_id)
        AgentService().delete_agent(request.user, agent)
        return Response(status=204)
