from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
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
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.agent.service import AgentService
from baserow.core.operations import UpdateApplicationOperationType
from baserow.core.subjects import UserSubjectType
from baserow_enterprise.api.field_permissions.serializers import (
    FieldPermissionSubjectOptionResponseSerializer,
    FieldPermissionSubjectOptionsRequestSerializer,
    FieldPermissionSubjectRequestSerializer,
    FieldPermissionSubjectResponseSerializer,
)
from baserow_enterprise.features import RBAC
from baserow_enterprise.field_permissions.models import FieldPermissionsRoleEnum
from baserow_enterprise.teams.subjects import TeamSubjectType
from baserow_premium.license.handler import LicenseHandler

from .models import AgentParticipationRule
from .service import update_rule


class RuleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(
        choices=[role.value for role in FieldPermissionsRoleEnum]
    )
    subjects = FieldPermissionSubjectRequestSerializer(
        many=True, required=False, default=list
    )


class AgentRuleResponseSerializer(RuleSerializer):
    subjects = FieldPermissionSubjectResponseSerializer(many=True, read_only=True)


class AgentRulesResponseSerializer(serializers.Serializer):
    chat = AgentRuleResponseSerializer()
    approve = AgentRuleResponseSerializer()


def get_agent(user, agent_id, *, edit=False, lock=False):
    agent = AgentService().get_authorized_agent(
        user,
        agent_id,
        ReadAgentConfigurationOperationType.type,
        *([UpdateApplicationOperationType.type] if edit else []),
        for_update=lock,
    )
    LicenseHandler.raise_if_user_doesnt_have_feature(RBAC, user, agent.workspace)
    return agent


def rule_data(rule):
    if not rule:
        return {"role": "EDITOR", "subjects": []}
    users = rule.users.filter(workspaceuser__workspace=rule.agent.workspace)
    teams = rule.teams.filter(workspace=rule.agent.workspace)
    return {
        "role": rule.role,
        "subjects": [
            *[
                {
                    "subject_type": UserSubjectType.type,
                    "subject_id": u.pk,
                    "subject": {
                        "id": u.pk,
                        "first_name": u.first_name,
                        "username": u.username,
                    },
                }
                for u in users
            ],
            *[
                {
                    "subject_type": TeamSubjectType.type,
                    "subject_id": t.pk,
                    "subject": {"id": t.pk, "name": t.name},
                }
                for t in teams
            ],
        ],
    }


class AgentRulesView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        parameters=[AGENT_ID_PATH_PARAMETER],
        responses=AgentRulesResponseSerializer,
    )
    @map_exceptions(AGENT_EXCEPTIONS)
    def get(self, request, agent_id):
        agent = get_agent(request.user, agent_id)
        rules = {
            rule.capability: rule
            for rule in AgentParticipationRule.objects.filter(agent=agent)
        }
        return Response(
            {
                cap: rule_data(rules.get(cap))
                for cap in AgentParticipationRule.Capability.values
            }
        )


class AgentRuleView(APIView):
    @extend_schema(
        tags=["Agent applications"],
        parameters=[AGENT_ID_PATH_PARAMETER],
        request=RuleSerializer,
        responses=AgentRuleResponseSerializer,
    )
    @transaction.atomic
    @map_exceptions(AGENT_EXCEPTIONS)
    @validate_body(RuleSerializer, return_validated=True)
    def put(self, request, agent_id, capability, data):
        agent = get_agent(request.user, agent_id, edit=True, lock=True)
        rule = update_rule(agent, capability, data["role"], data["subjects"])
        return Response(rule_data(rule))


class AgentRuleOptionsView(APIView):
    @extend_schema(
        tags=["Agent applications"],
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
    def get(self, request, agent_id, query_params):
        workspace = get_agent(request.user, agent_id, edit=True).workspace
        search = query_params["search"] or ""
        users = (
            UserSubjectType()
            .get_options_queryset(workspace, search, query_params["exclude_user_ids"])
            .filter(subject_user_type="human")
        )
        teams = TeamSubjectType().get_options_queryset(
            workspace, search, query_params["exclude_team_ids"]
        )
        options = users.union(teams).order_by(
            "subject_name", "subject_type", "subject_id"
        )
        paginator = PageNumberPagination(limit_page_size=100)
        page = paginator.paginate_queryset(options, request, view=self)
        return paginator.get_paginated_response(
            FieldPermissionSubjectOptionResponseSerializer(page, many=True).data
        )
