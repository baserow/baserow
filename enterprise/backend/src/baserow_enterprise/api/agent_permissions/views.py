from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_query_parameters,
)
from baserow.api.pagination import PageNumberPagination
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.contrib.agent.api.views import AGENT_EXCEPTIONS, AGENT_ID_PATH_PARAMETER
from baserow_enterprise.agent_permissions.service import AgentParticipationService
from baserow_enterprise.api.field_permissions.serializers import (
    FieldPermissionSubjectOptionResponseSerializer,
    FieldPermissionSubjectOptionsRequestSerializer,
)

from .serializers import (
    AgentParticipationRuleResponseSerializer,
    AgentParticipationRuleSerializer,
    AgentParticipationRulesResponseSerializer,
    serialize_rule,
)


class AgentParticipationRulesView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="get_agent_participation_rules",
        description=(
            "Lists who may chat with the agent, approve its tool calls and continue "
            "its triggered conversations, with each default where no rule is set."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER],
        responses=AgentParticipationRulesResponseSerializer,
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request: Request, agent_id: int) -> Response:
        """Lists the rule of each capability."""

        rules = AgentParticipationService().get_rules(request.user, agent_id)
        return Response(
            {
                capability: serialize_rule(rule, capability)
                for capability, rule in rules.items()
            }
        )


class AgentParticipationRuleView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="update_agent_participation_rule",
        description=(
            "Replaces the rule of one capability: `chat`, `approve` or `continue`. "
            "Saving its default role removes the rule."
        ),
        parameters=[AGENT_ID_PATH_PARAMETER],
        request=AgentParticipationRuleSerializer,
        responses=AgentParticipationRuleResponseSerializer,
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(AgentParticipationRuleSerializer, return_validated=True)
    def put(
        self, request: Request, agent_id: int, capability: str, data: dict
    ) -> Response:
        """Replaces the rule of one capability."""

        rule = AgentParticipationService().update_rule(
            request.user, agent_id, capability, data["role"], data["subjects"]
        )
        return Response(serialize_rule(rule, capability))


class AgentParticipationRuleOptionsView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        operation_id="list_agent_participation_rule_options",
        description="Lists the people and teams a `CUSTOM` rule can name.",
        parameters=[
            AGENT_ID_PATH_PARAMETER,
            FieldPermissionSubjectOptionsRequestSerializer,
        ],
        responses=get_example_pagination_serializer_class(
            FieldPermissionSubjectOptionResponseSerializer
        ),
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_query_parameters(
        FieldPermissionSubjectOptionsRequestSerializer, return_validated=True
    )
    def get(self, request: Request, agent_id: int, query_params: dict) -> Response:
        """Lists people and teams for a `CUSTOM` rule, a page at a time."""

        options = AgentParticipationService().list_subject_options(
            request.user,
            agent_id,
            query_params["search"] or "",
            query_params["exclude_user_ids"],
            query_params["exclude_team_ids"],
        )
        paginator = PageNumberPagination(limit_page_size=100)
        page = paginator.paginate_queryset(options, request, view=self)
        return paginator.get_paginated_response(
            FieldPermissionSubjectOptionResponseSerializer(page, many=True).data
        )
