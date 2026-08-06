from typing import List

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _

from baserow.core.models import Workspace
from baserow.core.registries import SubjectType
from baserow.core.types import Subject
from baserow_enterprise.api.role.serializers import SubjectTeamSerializer
from baserow_enterprise.teams.models import Team, TeamSubject

User = get_user_model()


class TeamSubjectType(SubjectType):
    type = "baserow_enterprise.Team"
    model_class = Team

    def get_type_display_name(self):
        return _("Team")

    def get_display_name(self, subject: Team) -> str:
        return subject.name

    def are_in_workspace(
        self,
        subjects: List[Subject],
        workspace: Workspace,
        include_trash: bool = False,
    ) -> List[bool]:
        team_manager = Team.objects_and_trash if include_trash else Team.objects
        team_ids_in_workspace = set(
            team_manager.filter(
                id__in=[s.id for s in subjects],
                workspace=workspace,
            ).values_list("id", flat=True)
        )

        return [t.id in team_ids_in_workspace for t in subjects]

    def get_serializer(self, model_instance, **kwargs):
        return SubjectTeamSerializer(model_instance, **kwargs)

    def get_users_included_in_subject(self, subject: Team) -> List[AbstractUser]:
        return list(
            User.objects.filter(
                pk__in=TeamSubject.objects_and_trash.filter(
                    team_id=subject.id,
                    subject_type=ContentType.objects.get_for_model(User),
                ).values_list("subject_id", flat=True)
            )
        )
