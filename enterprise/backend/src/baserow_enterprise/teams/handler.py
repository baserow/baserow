from collections import defaultdict
from typing import Any, Dict, List, NewType, Optional, Union, cast

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, IntegrityError, connection
from django.db.models import Count, OuterRef, QuerySet, Subquery
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce

from baserow.core.agents.subjects import AgentSubjectType
from baserow.core.exceptions import WorkspaceInvitationLinkSignupsDisabled
from baserow.core.feature_flags import FF_RBAC_IMPROVEMENTS, feature_flag_is_enabled
from baserow.core.handler import CoreHandler
from baserow.core.mixins import TrashableModelMixin
from baserow.core.models import (
    Workspace,
    WorkspaceInvitation,
    WorkspaceInvitationLink,
)
from baserow.core.operations import (
    CreateInvitationLinkWorkspaceOperationType,
    ListInvitationsWorkspaceOperationType,
)
from baserow.core.registries import subject_type_registry
from baserow.core.subjects import UserSubjectType
from baserow.core.trash.handler import TrashHandler
from baserow.core.user.utils import normalize_email_address
from baserow.core.utils import atomic_if_not_already
from baserow_enterprise.models import (
    Role,
    RoleAssignment,
    Team,
    TeamSubject,
    WorkspaceTeamInvitation,
)
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.signals import (
    team_created,
    team_deleted,
    team_subject_created,
    team_subject_deleted,
    team_updated,
)
from baserow_enterprise.teams.exceptions import (
    TeamDoesNotExist,
    TeamInvitationDoesNotExist,
    TeamNameNotUnique,
    TeamSubjectBadRequest,
    TeamSubjectBulkDoesNotExist,
    TeamSubjectDoesNotExist,
    TeamSubjectNotInGroup,
    TeamSubjectTypeUnsupported,
)
from baserow_enterprise.teams.operations import (
    CreateTeamSubjectOperationType,
    ListTeamSubjectsOperationType,
)
from baserow_premium.license.handler import LicenseHandler

from ..features import TEAMS

TeamForUpdate = NewType("TeamForUpdate", Team)
TeamSubjectForUpdate = NewType("TeamSubjectForUpdate", TeamSubject)

SUPPORTED_SUBJECT_TYPES = (UserSubjectType.type, AgentSubjectType.type)


class TeamHandler:
    def get_team_subjects_queryset(self) -> QuerySet:
        """Hide trashed subjects while retaining memberships for their restoration."""
        queryset = TeamSubject.objects.all()
        for subject_type in subject_type_registry.get_all():
            if issubclass(subject_type.model_class, TrashableModelMixin):
                # IDs can overlap across subject types, so filter by both fields.
                queryset = queryset.exclude(
                    subject_type=subject_type.get_content_type(),
                    subject_id__in=subject_type.model_class.trash.values("id"),
                )
        return queryset

    def get_teams_queryset(self) -> QuerySet:
        """
        Responsible for returning a `Team` queryset with an annotated
        `subject_count`, which represents the total number of subjects in the team.

        Needs to narrowed down further to select a specific ID or Group.
        """

        subj_count = (
            self.get_team_subjects_queryset()
            .filter(team_id=OuterRef("id"))
            .order_by()
            .values("team_id")
            .annotate(count=Count("*"))
            .values("count")
        )

        return Team.objects.annotate(
            subject_count=Coalesce(Subquery(subj_count), 0),
            _annotated_default_role_uid=Subquery(
                RoleAssignment.objects.select_related("role")
                .filter(
                    scope_id=OuterRef("workspace_id"),
                    workspace_id=OuterRef("workspace_id"),
                    scope_type=ContentType.objects.get_for_model(Workspace),
                    subject_type=ContentType.objects.get_for_model(Team),
                    subject_id=OuterRef("id"),
                )
                .values("role__uid")
            ),
        )

    def get_teams_sample_queryset(self, subject_sample_size: int = 10) -> QuerySet:
        """
        Responsible for taking the queryset in `get_teams_queryset` and annotating
        it further with a `subject_sample`, an array of the last `subject_sample_size`
        subjects to be invited to the team.

        Needs to narrowed down further to select a specific ID or Group.
        """

        subject_label_cases = []
        subject_joins = []
        case_params = []
        join_params = []
        quote_name = connection.ops.quote_name

        # Each supported subject type has its own database table. Build one
        # conditional label case and one matching join for each of those tables.
        for index, subject_type_name in enumerate(SUPPORTED_SUBJECT_TYPES):
            table_alias = f"team_subject_{index}"
            subject_type = subject_type_registry.get(subject_type_name)
            model_class = subject_type.model_class
            model_meta = model_class._meta

            display_name_field = subject_type.display_name_field
            if display_name_field is None:
                raise TeamSubjectTypeUnsupported(
                    f"The subject type {subject_type_name} has no display name field."
                )

            label_column = model_meta.get_field(display_name_field).column
            type_condition = "ct.app_label = %s AND ct.model = %s"
            type_params = [model_meta.app_label, model_meta.model_name]

            # Select the label from the table matching the subject's content type.
            subject_label_cases.append(
                f"WHEN ({type_condition}) THEN {table_alias}.{quote_name(label_column)}"
            )
            case_params.extend(type_params)

            # Restrict the join by content type because subject IDs can overlap
            # between the different subject tables.
            subject_joins.append(
                f"LEFT OUTER JOIN {quote_name(model_meta.db_table)} {table_alias} "
                f"ON ({table_alias}.id = sub.subject_id AND {type_condition})"
            )
            join_params.extend(type_params)

        # Use the same visibility rules for samples, counts, and member lists.
        # Filter before LIMIT so hidden subjects don't consume sample slots.
        visible_subjects_sql, visible_subjects_params = (
            self.get_team_subjects_queryset()
            .order_by()
            .values("id")
            .query.sql_with_params()
        )
        # Placeholder order follows CASE, JOIN, visibility filter, then LIMIT.
        subject_sample_params = [
            *case_params,
            *join_params,
            *visible_subjects_params,
            subject_sample_size,
        ]

        subject_sample_sql = f"""
            SELECT COALESCE(json_agg(sub), '[]') FROM (
                SELECT
                    sub.id AS team_subject_id,
                    sub.subject_id,
                    CONCAT(ct.app_label, '.', INITCAP(ct.model)) AS subject_type,
                    CASE
                        {" ".join(subject_label_cases)}
                    END AS subject_label
                FROM baserow_enterprise_teamsubject sub
                INNER JOIN django_content_type ct ON (ct.id = sub.subject_type_id)
                {" ".join(subject_joins)}
                WHERE sub.team_id = baserow_enterprise_team.id
                    AND sub.id IN ({visible_subjects_sql})
                ORDER BY sub.created_on DESC
                LIMIT %s
            ) sub
        """  # noqa: S608

        return self.get_teams_queryset().annotate(
            subject_sample=RawSQL(  # nosec
                subject_sample_sql,
                subject_sample_params,
            ),
        )

    def list_teams_in_workspace(
        self, user: AbstractUser, workspace: Workspace, subject_sample_size: int = 10
    ) -> QuerySet:
        """
        Returns a list of teams in a given workspace.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, workspace)

        return self.get_teams_sample_queryset(subject_sample_size).filter(
            workspace=workspace
        )

    def get_team(self, user: AbstractUser, team_id: int, base_queryset=None) -> Team:
        """
        Selects a team with a given id from the database.
        """

        if base_queryset is None:
            base_queryset = self.get_teams_queryset()

        try:
            team = base_queryset.get(id=team_id)
        except Team.DoesNotExist:
            raise TeamDoesNotExist(f"The team with id {team_id} does not exist.")

        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, team.workspace)

        return team

    def get_team_for_update(self, user, team_id: int) -> TeamForUpdate:
        return cast(
            TeamForUpdate,
            self.get_team(
                user,
                team_id,
                base_queryset=Team.objects.select_for_update(of=("self",)),
            ),
        )

    def create_team(
        self,
        user: AbstractUser,
        name: str,
        workspace: Workspace,
        subjects: Optional[List[Dict]] = None,
        default_role: Optional[Role] = None,
    ) -> Team:
        """
        Creates a new team for an existing workspace.
        Can optionally be given an array of subjects to create at the same time.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, workspace)

        if subjects is None:
            subjects = []

        with atomic_if_not_already():
            try:
                team = Team.objects.create(workspace=workspace, name=name)
            except IntegrityError as e:
                if "unique constraint" in e.args[0]:
                    raise TeamNameNotUnique(name=name)
                raise e

            for subject in subjects:
                self.create_subject(
                    user, {"id": subject["subject_id"]}, subject["subject_type"], team
                )

        # If we've been given a `default_role`, assign it to the team.
        RoleAssignmentHandler().assign_role(team, workspace, default_role)

        team_created.send(self, team_id=team.id, team=team, user=user)

        return self.get_team(
            user, team.id, base_queryset=self.get_teams_sample_queryset()
        )

    def update_team(
        self,
        user: AbstractUser,
        team: Team,
        name: str,
        subjects: Optional[List[Dict]] = None,
        default_role: Optional[Role] = None,
    ) -> Team:
        """
        Updates an existing team instance. The members of the team are replaced by
        `subjects`, unless it is `None`, which leaves them as they are.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, team.workspace)

        # In a transaction...
        # 1. Update the name field.
        # 2. Fetch the existing subjects and workspace them by their type.
        # 3. Create any new subjects we've been given.
        # 4. Remove any existing subjects we don't want anymore.
        with atomic_if_not_already():
            try:
                team.name = name
                team.save(update_fields=["name"])
            except DatabaseError:
                raise TeamNameNotUnique(name=name)

            if subjects is not None:
                # Build a default dict of existing subjects in the team. The key is the
                # `TeamSubject.subject_type_natural_key`, then the `subject_id`. Keep
                # every membership ID so removing a subject also removes duplicates.
                existing_subjects = defaultdict(lambda: defaultdict(list))
                # Trashed subjects are absent from the edit form. Preserve their
                # memberships so saving visible members does not break restoration.
                existing_subject_qs = self.list_subjects_in_team(team.id)
                for existing_subject in existing_subject_qs:
                    existing_subjects[existing_subject.subject_type_natural_key][
                        existing_subject.subject_id
                    ].append(existing_subject.id)

                # Loop over the subjects we've been given. If the `subject_id`
                # isn't present in our `existing_subjects` dict, keyed by the
                # `subject_type`, then it's a new subject.
                for subject in subjects:
                    subject_id = subject["subject_id"]
                    subject_type = subject["subject_type"]
                    if subject_id not in existing_subjects[subject_type]:
                        self.create_subject(
                            user, {"id": subject_id}, subject_type, team
                        )

                # Determine if any existing subjects need to be removed.
                for existing_type, existing_subject_ids in existing_subjects.items():
                    # Find all the subjects in `subjects` which
                    # have the `subject_type` we're looping over.
                    payload_subjects_for_type = filter(
                        lambda payload_sub: (
                            payload_sub["subject_type"] == existing_type
                        ),
                        subjects,
                    )
                    # Pluck out the subject IDs of this `subject_type`.
                    payload_subject_ids_for_type = [
                        payload["subject_id"] for payload in payload_subjects_for_type
                    ]
                    # Find the difference between `existing_type_ids`
                    # and `payload_subject_ids_for_type`
                    removed_subjects = list(
                        set(existing_subject_ids) - set(payload_subject_ids_for_type)
                    )
                    for removed_subject_id in removed_subjects:
                        for membership_id in existing_subject_ids[removed_subject_id]:
                            self.delete_subject_by_id(user, membership_id, team)

            # If we've been given a `default_role`, assign it to the team.
            RoleAssignmentHandler().assign_role(team, team.workspace, default_role)

        team_updated.send(self, team=team, user=user)

        return self.get_team(
            user, team.id, base_queryset=self.get_teams_sample_queryset()
        )

    def delete_team(self, user: AbstractUser, team: TeamForUpdate):
        """
        Deletes an existing team if the user has admin permissions for the workspace.
        The team can be restored after deletion using the trash handler.
        """

        if not isinstance(team, Team):
            raise ValueError("The team is not an instance of Team.")

        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, team.workspace)

        TrashHandler.trash(user, team.workspace, None, team)

        team_deleted.send(self, team_id=team.id, team=team, user=user)

    def get_teamsubject_subject_qs(self, subject, base_queryset=None) -> QuerySet:
        """Return visible memberships belonging to a subject."""

        if base_queryset is None:
            base_queryset = self.get_team_subjects_queryset()

        return base_queryset.filter(
            subject_id=subject.id,
            subject_type=ContentType.objects.get_for_model(subject),
        )

    def get_subject(
        self, subject_id: int, team: Team, base_queryset=None
    ) -> TeamSubject:
        """
        Selects a subject with a given `id` and `Team` from the database.

        """

        if base_queryset is None:
            base_queryset = self.get_team_subjects_queryset()

        try:
            subject = base_queryset.select_related("subject_type").get(
                id=subject_id, team=team
            )
        except TeamSubject.DoesNotExist:
            raise TeamSubjectDoesNotExist(
                f"The subject with id {subject_id} does not exist."
            )

        return subject

    def is_supported_subject_type(self, subject_natural_key: str) -> bool:
        """
        Confirms if a content type natural key is supported.
        """

        return subject_natural_key in SUPPORTED_SUBJECT_TYPES

    def bulk_create_subjects(
        self, team: Team, subjects: List[Dict[str, Any]], raise_on_missing: bool = True
    ) -> List[TeamSubject]:
        """ """

        # The list which will store our subject model instances.
        subject_models = []

        # A default dict which stores the unique ID we want to
        # create the `TeamSubject` with. Used by actions when we
        # revert the deletion of a team's subjects.
        pk_overrides = defaultdict(lambda: defaultdict(int))

        # Find the unique subject types in the `subjects` we've been given.
        unique_subject_types = list(
            set(map(lambda subject: subject["subject_type"], subjects))
        )

        # For each unique subject type we found.
        for unique_subject_type in unique_subject_types:
            # Build a list of unique subject IDs, of this type.
            subject_ids_of_type = []

            # Find the model class for this `subject_type`.
            model_class = subject_type_registry.get(unique_subject_type).model_class

            # Find the subjects we've been given for this `subject_type`...
            subjects_of_type = filter(
                lambda s: s["subject_type"] == unique_subject_type, subjects
            )
            for subject_of_type in subjects_of_type:
                # Store the subject's PK.
                subject_id = subject_of_type["subject_id"]
                subject_ids_of_type.append(subject_id)

                # If we've been given a `pk` value, store it for later use.
                pk_override = subject_of_type.get("pk", None)
                if pk_override:
                    pk_overrides[unique_subject_type][subject_id] = pk_override

            # TODO: if we support a subject type that doesn't have a `workspace`
            #   relation on its model, then this filter need to be modified.
            type_subject_models = model_class.objects.filter(
                pk__in=subject_ids_of_type, workspace=team.workspace_id
            )

            # If the subjects we found don't match those in `subject_ids_of_type`,
            # and we want to raise an exception if a subject isn't found, work out
            # what the missing ones are and raise an exception.
            if (
                len(type_subject_models) != len(subject_ids_of_type)
                and raise_on_missing
            ):
                missing_subjects = []
                ids_found = list(map(lambda model: model.id, type_subject_models))
                missing_ids = list(set(subject_ids_of_type) - set(ids_found))
                for missing_id in missing_ids:
                    missing_subjects.append(
                        {
                            "subject_id": missing_id,
                            "subject_type": unique_subject_type,
                        }
                    )
                raise TeamSubjectBulkDoesNotExist(missing_subjects)

            subject_models.extend(type_subject_models)

        # We now have a list of subject models, loop over them, set a `pk`
        # if we were given one in `subjects` and then bulk create their
        # corresponding `TeamSubject` models.
        bulk_teamsubjects = []
        for subject_model in subject_models:
            subj_kwargs = {"team": team, "subject": subject_model}
            pk_override = pk_overrides[subject_model._meta.label][subject_model.pk]
            if pk_override:
                subj_kwargs["pk"] = pk_override
            bulk_teamsubjects.append(TeamSubject(**subj_kwargs))

        return TeamSubject.objects.bulk_create(bulk_teamsubjects)

    def create_subject(
        self,
        user: AbstractUser,
        subject_lookup: Dict[str, Union[str, int]],
        subject_natural_key: str,
        team: Team,
    ) -> TeamSubject:
        """
        Creates a new subject for a given team.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, team.workspace)

        # Determine if this `TeamSubject` content type natural key is supported.
        if not self.is_supported_subject_type(subject_natural_key):
            raise TeamSubjectTypeUnsupported(
                f"The subject type {subject_natural_key} is unsupported."
            )

        subject_type = subject_type_registry.get(subject_natural_key)
        unexpected_lookups = [
            lookup
            for lookup in subject_lookup
            if not subject_type.supports_lookup_field(lookup)
        ]
        if unexpected_lookups:
            raise TeamSubjectBadRequest(
                f"A subject cannot be created with lookups {', '.join(unexpected_lookups)}."
            )

        # Get the model for this `subject_natural_key`.
        model_class = subject_type.model_class

        try:
            subject = model_class.objects.get(**subject_lookup)
        except model_class.DoesNotExist:
            lookup_str = ", ".join([f"{k}={v}" for k, v in subject_lookup.items()])
            raise TeamSubjectDoesNotExist(
                f"The subject with {lookup_str} and type={subject_natural_key} does not exist."
            )

        if not subject_type.is_in_workspace(subject, team.workspace):
            raise TeamSubjectNotInGroup()

        subject = TeamSubject.objects.create(team=team, subject=subject)

        team_subject_created.send(
            self, subject_id=subject.id, subject=subject, user=user
        )

        return subject

    def list_subjects_in_team(self, team_id: int) -> QuerySet:
        """
        Returns a list of subjects in a given workspace.
        """

        return (
            self.get_team_subjects_queryset()
            .select_related("subject_type")
            .filter(team=team_id)
        )

    def get_subject_for_update(
        self, subject_id: int, team: Team
    ) -> TeamSubjectForUpdate:
        """Lock a visible membership before modifying it."""
        return cast(
            TeamSubjectForUpdate,
            self.get_subject(
                subject_id,
                team,
                base_queryset=self.get_team_subjects_queryset().select_for_update(
                    of=("self",)
                ),
            ),
        )

    def delete_subject_by_id(self, user: AbstractUser, subject_id: int, team: Team):
        """
        Deletes a subject by id, only if the user has admin permissions
        for the workspace.
        """

        locked_subject = self.get_subject_for_update(subject_id, team)
        self.delete_subject(user, locked_subject)

    def delete_subject(self, user: AbstractUser, subject: TeamSubjectForUpdate):
        """
        Deletes an existing subject if the user has admin permissions for the workspace.
        The subject can be restored after deletion using the trash handler.
        """

        if not isinstance(subject, TeamSubject):
            raise ValueError("The subject is not an instance of TeamSubject.")

        LicenseHandler.raise_if_user_doesnt_have_feature(
            TEAMS, user, subject.team.workspace
        )

        subject.delete()

        team_subject_deleted.send(
            self, subject_id=subject.id, subject=subject, user=user
        )

    def create_team_invitation(
        self, user: AbstractUser, team: Team, email: str
    ) -> WorkspaceTeamInvitation:
        """
        Invites the given email address to a team. The person joins the workspace
        with the `NO_ROLE_LOW_PRIORITY` workspace role, so that the role of the team
        applies, and is added to the team once they accept. If a pending invitation
        already exists for the address it is reused: its workspace role is kept as it
        is and the team is added to it, so one invitation can add the person to
        several teams. Inviting the same address to the same team again sends the
        invitation email again.

        :param user: The user on whose behalf the invitation is created.
        :param team: The team the person is invited to.
        :param email: The email address of the person that is invited.
        :raises WorkspaceUserAlreadyExists: If the address already belongs to a
            member of the workspace, who should be added to the team directly.
        :return: The created or existing team invitation.
        """

        workspace = team.workspace
        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, workspace)
        CoreHandler().check_permissions(
            user,
            CreateTeamSubjectOperationType.type,
            workspace=workspace,
            context=team,
        )

        email = normalize_email_address(email)
        existing_invitation = WorkspaceInvitation.objects.filter(
            workspace=workspace, email=email
        ).first()
        permissions = (
            existing_invitation.permissions
            if existing_invitation
            else NO_ROLE_LOW_PRIORITY_ROLE_UID
        )
        invitation = CoreHandler().create_workspace_invitation(
            user, workspace, email, permissions
        )

        team_invitation, _ = WorkspaceTeamInvitation.objects.get_or_create(
            invitation=invitation, team=team
        )
        return team_invitation

    def list_team_invitations(
        self, user: AbstractUser, team: Team
    ) -> QuerySet[WorkspaceTeamInvitation]:
        """
        Returns the pending invitations to a team. They hold email addresses, so the
        user must be allowed to list the invitations of the workspace as well as the
        members of the team.

        :param user: The user on whose behalf the invitations are listed.
        :param team: The team the invitations add people to.
        :return: A queryset of the team invitations, oldest first.
        """

        workspace = team.workspace
        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, workspace)
        CoreHandler().check_permissions(
            user,
            ListTeamSubjectsOperationType.type,
            workspace=workspace,
            context=team,
        )
        CoreHandler().check_permissions(
            user,
            ListInvitationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        return WorkspaceTeamInvitation.objects.filter(team=team).select_related(
            "invitation"
        )

    def get_team_invitation(
        self, team_invitation_id: int, team: Team
    ) -> WorkspaceTeamInvitation:
        """
        Returns the invitation with the given id to the given team.

        :param team_invitation_id: The id of the team invitation.
        :param team: The team the invitation must belong to.
        :raises TeamInvitationDoesNotExist: If it doesn't exist.
        :return: The team invitation with its invitation loaded.
        """

        try:
            return WorkspaceTeamInvitation.objects.select_related(
                "invitation", "team__workspace"
            ).get(id=team_invitation_id, team=team)
        except WorkspaceTeamInvitation.DoesNotExist:
            raise TeamInvitationDoesNotExist(
                f"The team invitation with id {team_invitation_id} does not exist."
            )

    def delete_team_invitation(
        self, user: AbstractUser, team_invitation: WorkspaceTeamInvitation
    ):
        """
        Revokes the invitation of a person to a team. Only the team is removed, the
        workspace invitation itself and the other teams or objects it carries are
        kept.

        :param user: The user revoking the team invitation.
        :param team_invitation: The team invitation to delete.
        """

        team = team_invitation.team
        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, team.workspace)
        # Whoever can invite someone to the team can take that invitation back.
        CoreHandler().check_permissions(
            user,
            CreateTeamSubjectOperationType.type,
            workspace=team.workspace,
            context=team,
        )

        team_invitation.delete()

    def add_invitee_to_teams(
        self, invitation: WorkspaceInvitation, user: AbstractUser
    ) -> List[TeamSubject]:
        """
        Adds the user who accepted a workspace invitation to the teams the
        invitation carries. Teams that were trashed in the meantime, or that the
        user is already in, are skipped, and so are all of them if the workspace
        lost the teams feature, so the person always joins the workspace.

        :param invitation: The accepted invitation, still carrying its teams.
        :param user: The user who accepted it and is now a member of the workspace.
        :return: The created team subjects.
        """

        if not LicenseHandler.workspace_has_feature(TEAMS, invitation.workspace):
            return []

        team_subjects = []
        for team_invitation in invitation.team_invitations.select_related(
            "team__workspace"
        ):
            team = team_invitation.team
            if team.trashed:
                continue
            if self.get_teamsubject_subject_qs(user).filter(team=team).exists():
                continue
            team_subjects.append(
                self.create_subject(user, {"id": user.id}, UserSubjectType.type, team)
            )
        return team_subjects

    def _check_invitation_link_permissions(self, user: AbstractUser, team: Team):
        """
        Runs the checks that guard managing the invitation links of a team. Links
        add people to the team and bring newcomers into the workspace, so the user
        must be allowed to add members to the team and to create invitation links
        to the workspace.

        :param user: The user managing the links of the team.
        :param team: The team the links add people to.
        :raises FeatureDisabledException: If invitation links aren't enabled.
        :raises FeatureNotAvailable: If the workspace doesn't have teams.
        :raises PermissionDenied: If the user isn't allowed to manage the links.
        """

        feature_flag_is_enabled(FF_RBAC_IMPROVEMENTS, raise_if_disabled=True)

        workspace = team.workspace
        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, workspace)
        CoreHandler().check_permissions(
            user,
            CreateTeamSubjectOperationType.type,
            workspace=workspace,
            context=team,
        )
        CoreHandler().check_permissions(
            user,
            CreateInvitationLinkWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

    def _get_team_invitation_links_queryset(
        self, team: Team
    ) -> QuerySet[WorkspaceInvitationLink]:
        return WorkspaceInvitationLink.objects.filter(
            workspace_id=team.workspace_id,
            scope_type=ContentType.objects.get_for_model(Team),
            scope_id=team.id,
        )

    def list_team_invitation_links(
        self, user: AbstractUser, team: Team
    ) -> QuerySet[WorkspaceInvitationLink]:
        """
        Returns the permanent invitation links to a team. Anyone with a link can
        use it, so listing them needs the same rights as managing them.

        :param user: The user on whose behalf the links are listed.
        :param team: The team the links add people to.
        :return: A queryset of the links of the team, oldest first.
        """

        self._check_invitation_link_permissions(user, team)
        return self._get_team_invitation_links_queryset(team).order_by("id")

    def get_team_invitation_link(
        self, invitation_link_id: int, team: Team
    ) -> WorkspaceInvitationLink:
        """
        Returns the invitation link with the given id to the given team.

        :param invitation_link_id: The id of the invitation link.
        :param team: The team the link must add people to.
        :raises WorkspaceInvitationLinkDoesNotExist: If the team has no such link.
        :return: The invitation link with its workspace loaded.
        """

        return CoreHandler().get_workspace_invitation_link(
            invitation_link_id,
            base_queryset=self._get_team_invitation_links_queryset(team),
        )

    def create_team_invitation_link(
        self, user: AbstractUser, team: Team, name: str = ""
    ) -> WorkspaceInvitationLink:
        """
        Creates a permanent link that anyone can use to join the team. People who
        aren't a member of the workspace yet join it without a workspace role, so
        that the role of the team applies to them, and members of the workspace
        are added to the team. The link itself has no role: the team gives it.

        :param user: The user on whose behalf the link is created.
        :param team: The team the link adds people to.
        :param name: A name that reminds the admins what the link is for.
        :raises WorkspaceInvitationLinkSignupsDisabled: If the instance settings
            don't let anyone sign up through the link.
        :return: The created invitation link.
        """

        self._check_invitation_link_permissions(user, team)

        if not CoreHandler().invitation_link_signups_allowed():
            raise WorkspaceInvitationLinkSignupsDisabled(
                "Invitation links can't be created while signups are disabled."
            )

        return WorkspaceInvitationLink.objects.create(
            workspace=team.workspace,
            created_by=user,
            # The workspace role of newcomers, which lets the team's role apply.
            permissions=NO_ROLE_LOW_PRIORITY_ROLE_UID,
            name=name,
            scope=team,
        )

    def update_team_invitation_link(
        self,
        user: AbstractUser,
        team: Team,
        invitation_link: WorkspaceInvitationLink,
        name: str,
    ) -> WorkspaceInvitationLink:
        """
        Changes the name of a link to a team.

        :param user: The user on whose behalf the link is updated.
        :param team: The team of the link.
        :param invitation_link: The link that must be updated.
        :param name: The new name of the link.
        :return: The updated invitation link.
        """

        self._check_invitation_link_permissions(user, team)

        invitation_link.name = name
        invitation_link.save(update_fields=["name", "updated_on"])
        return invitation_link

    def delete_team_invitation_link(
        self, user: AbstractUser, team: Team, invitation_link: WorkspaceInvitationLink
    ):
        """
        Deletes a link to a team, after which it can't be used anymore. People who
        joined through it stay in the team.

        :param user: The user on whose behalf the link is deleted.
        :param team: The team of the link.
        :param invitation_link: The link that must be deleted.
        """

        self._check_invitation_link_permissions(user, team)
        invitation_link.delete()
