from collections import defaultdict
from typing import Any, Dict, List, NewType, Optional, Union, cast

from django.contrib.auth.models import AbstractUser, User
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, IntegrityError
from django.db.models import Count, OuterRef, QuerySet, Subquery
from django.db.models.expressions import RawSQL
from django.db.models.functions import Coalesce

from baserow.contrib.database.tokens.models import Token
from baserow.core.models import Workspace
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import atomic_if_not_already
from baserow_enterprise.models import Role, RoleAssignment, Team, TeamSubject
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.signals import (
    team_created,
    team_deleted,
    team_subject_created,
    team_subject_deleted,
    team_subject_restored,
    team_updated,
)
from baserow_enterprise.teams.exceptions import (
    TeamDoesNotExist,
    TeamNameNotUnique,
    TeamSubjectBadRequest,
    TeamSubjectBulkDoesNotExist,
    TeamSubjectDoesNotExist,
    TeamSubjectNotInGroup,
    TeamSubjectTypeUnsupported,
)
from baserow_premium.license.handler import LicenseHandler

from ..features import TEAMS

TeamForUpdate = NewType("TeamForUpdate", Team)
TeamSubjectForUpdate = NewType("TeamSubjectForUpdate", TeamSubject)

SUBJECT_TYPE_USER = "auth.User"
SUBJECT_TYPE_TOKEN = "database.Token"  # nosec
SUPPORTED_SUBJECT_TYPES = {SUBJECT_TYPE_USER: User}


class TeamHandler:
    def get_teams_queryset(self) -> QuerySet:
        """
        Responsible for returning a `Team` queryset with an annotated
        `subject_count`, which represents the total number of subjects in the team.

        Needs to narrowed down further to select a specific ID or Group.
        """

        subj_count = (
            TeamSubject.objects.filter(team_id=OuterRef("id"))
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

        subject_sample_sql = """
            SELECT COALESCE(json_agg(sub), '[]') FROM (
                SELECT
                    sub.id AS team_subject_id,
                    sub.subject_id,
                    CONCAT(ct.app_label, '.', INITCAP(ct.model)) AS subject_type,
                    CASE
                        WHEN (ct.app_label = 'auth' AND ct.model = 'user')
                            THEN auth_user.first_name
                    END AS subject_label
                FROM baserow_enterprise_teamsubject sub
                INNER JOIN django_content_type ct ON (ct.id = sub.subject_type_id)
                LEFT OUTER JOIN auth_user ON (
                    auth_user.id = sub.subject_id AND
                    ct.app_label = 'auth' AND
                    ct.model = 'user'
                )
                WHERE sub.team_id = baserow_enterprise_team.id
                ORDER BY sub.created_on DESC
                LIMIT %s
            ) sub
        """

        return self.get_teams_queryset().annotate(
            subject_sample=RawSQL(subject_sample_sql, [subject_sample_size]),  # nosec
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
        Updates an existing team instance.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, team.workspace)

        if subjects is None:
            subjects = []

        # In a transaction...
        # 1. Fetch the existing subjects and workspace them by their type.
        # 2. Update the name field.
        # 3. Create any new subjects we've been given.
        # 4. Remove any existing subjects we don't want anymore.
        with atomic_if_not_already():
            # Build a default dict of existing subjects in the team. The key is the
            # `TeamSubject.subject_type_natural_key`, the value contains the list of
            # `subject_id` of that `subject_type`. We'll use this to determine if there
            # are subjects to add, or remove.
            existing_subjects = defaultdict(list)
            existing_subject_qs = team.subjects.select_related("subject_type").all()
            for existing_subject in existing_subject_qs:
                existing_subjects[existing_subject.subject_type_natural_key].append(
                    existing_subject.id
                )

            try:
                team.name = name
                team.save(update_fields=["name"])
            except DatabaseError:
                raise TeamNameNotUnique(name=name)

            # Loop over the subjects we've been given. If the `subject_id`
            # isn't present in our `existing_subjects` dict, keyed by the
            # `subject_type`, then it's a new subject.
            for subject in subjects:
                subject_id = subject["subject_id"]
                subject_type = subject["subject_type"]
                if subject_id not in existing_subjects[subject_type]:
                    self.create_subject(user, {"id": subject_id}, subject_type, team)

            # Determine if any existing subjects need to be removed.
            for existing_type, existing_type_ids in existing_subjects.items():
                # Find all the subjects in `subjects` which
                # have the `subject_type` we're looping over.
                payload_subjects_for_type = filter(
                    lambda payload_sub: payload_sub["subject_type"] == existing_type,
                    subjects,
                )
                # Pluck out the subject IDs of this `subject_type`.
                payload_subject_ids_for_type = [
                    payload["subject_id"] for payload in payload_subjects_for_type
                ]
                # Find the difference between `existing_type_ids`
                # and `payload_subject_ids_for_type`
                removed_subjects = list(
                    set(existing_type_ids) - set(payload_subject_ids_for_type)
                )
                for removed_subject_id in removed_subjects:
                    self.delete_subject_by_id(user, removed_subject_id, team)

            # If we've been given a `default_role`, assign it to the team.
            RoleAssignmentHandler().assign_role(team, team.workspace, default_role)

        team_updated.send(self, team=team, user=user)

        return self.get_team(
            user, team.id, base_queryset=self.get_teams_sample_queryset()
        )

    def delete_team_by_id(self, user: AbstractUser, team_id: int):
        """
        Deletes a team by id, only if the user has admin permissions for the workspace.
        """

        locked_team = self.get_team_for_update(user, team_id)
        self.delete_team(user, locked_team)

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

    def restore_team_by_id(self, user: AbstractUser, team_id: int) -> Team:
        """
        Responsible for calling `restore_item` in `TrashHandler`, and once
        complete, re-fetching the newly restored `Team` so we can send a
        `team_restored` signal.
        """

        team = self.get_team(user, team_id, base_queryset=Team.objects_and_trash)
        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, team.workspace)
        TrashHandler.restore_item(user, "team", team_id)
        team.refresh_from_db()
        return team

    def get_teamsubject_subject_qs(self, subject, base_queryset=None) -> QuerySet:
        """ """

        if base_queryset is None:
            base_queryset = TeamSubject.objects

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
            base_queryset = TeamSubject.objects

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

        # The list which will store our `User` or `Token` subjects.
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
            model_class = SUPPORTED_SUBJECT_TYPES[unique_subject_type]

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
        pk: Optional[int] = None,
    ) -> TeamSubject:
        """
        Creates a new subject for a given team.

        If a `pk` is provided, we'll create a `TeamSubject` with an
        `id` of this value. This is used by the `TeamSubject` action
        redo to re-create a subject with the same PK.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(TEAMS, user, team.workspace)

        # Determine if this `TeamSubject` content type natural key is supported.
        if not self.is_supported_subject_type(subject_natural_key):
            raise TeamSubjectTypeUnsupported(
                f"The subject type {subject_natural_key} is unsupported."
            )

        # We only support creating a subject via an ID/PK or
        # in the case of a user, its email.
        permitted_lookups = ["id", "pk", "email"]
        unexpected_lookups = list(set(subject_lookup.keys()) - set(permitted_lookups))
        if unexpected_lookups:
            raise TeamSubjectBadRequest(
                f"A subject cannot be created with lookups {', '.join(unexpected_lookups)}."
            )

        # Get the model for this `subject_natural_key`.
        model_class = SUPPORTED_SUBJECT_TYPES[subject_natural_key]

        try:
            subject = model_class.objects.get(**subject_lookup)
        except model_class.DoesNotExist:
            lookup_str = ", ".join([f"{k}={v}" for k, v in subject_lookup.items()])
            raise TeamSubjectDoesNotExist(
                f"The subject with {lookup_str} and type={subject_natural_key} does not exist."
            )

        # Verify that the subject belongs to the workspace the team belongs to.
        if isinstance(subject, User):
            if not team.workspace.users.filter(
                workspaceuser__user_id=subject.id
            ).exists():
                raise TeamSubjectNotInGroup()
        elif isinstance(subject, Token):
            if subject.workspace_id != team.workspace_id:
                raise TeamSubjectNotInGroup()

        signal = team_subject_created
        create_kwargs = {"team": team, "subject": subject}
        if pk:
            create_kwargs["id"] = pk
            signal = team_subject_restored
        subject = TeamSubject.objects.create(**create_kwargs)

        signal.send(self, subject_id=subject.id, subject=subject, user=user)

        return subject

    def list_subjects_in_team(self, team_id: int) -> QuerySet:
        """
        Returns a list of subjects in a given workspace.
        """

        return TeamSubject.objects.select_related("subject_type").filter(team=team_id)

    def get_subject_for_update(
        self, subject_id: int, team: Team
    ) -> TeamSubjectForUpdate:
        return cast(
            TeamSubjectForUpdate,
            self.get_subject(
                subject_id,
                team,
                base_queryset=TeamSubject.objects.select_for_update(of=("self",)),
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
