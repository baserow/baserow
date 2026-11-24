from collections import defaultdict
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.crypto import salted_hmac

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger
from rest_framework.exceptions import ValidationError

from baserow.api.validators import no_url_validation
from baserow.core.exceptions import PermissionException
from baserow.core.identities.exceptions import IdentityCannotBeScoped
from baserow.core.identities.handler import IdentityHandler
from baserow.core.identities.registries import identity_extension_type_registry
from baserow.core.models import Application, IdentityDefinition, User, Workspace
from baserow.core.registries import ImportExportConfig, application_type_registry
from baserow.core.user.identity import IDENTITY_EMAIL_DOMAIN
from baserow.core.utils import exception_capturer, find_unused_name

# The part of an export or a template, beside its applications, that holds what a
# workspace owns and its applications refer to.
WORKSPACE_OBJECTS = "workspace_objects"
IDENTITIES = "identities"
APPLICATION_SCOPE = "application"
# The import's maps, kept in the `id_mapping` the applications are imported with.
DEFINITIONS_MAPPING = "identity_definitions"
EMAILS_MAPPING = "identity_emails"


def imported_identity_emails(id_mapping: dict) -> dict[str, User]:
    """
    :param id_mapping: The export-to-import id map.
    :return: The identities this import created, by the address the exported data
        refers to them by.
    """

    return id_mapping.get(EMAILS_MAPPING) or {}


def delete_unused_identity_definitions(definition_ids: list[int]) -> None:
    """
    Deletes the given definitions that nothing waits for any more. Anything that
    points at a definition counts, so a new kind of consumer needs no change here.

    :param definition_ids: The ids of the definitions something stopped waiting for.
    """

    unused = IdentityDefinition.objects.filter(id__in=definition_ids)
    for relation in IdentityDefinition._meta.related_objects:
        unused = unused.filter(**{f"{relation.name}__isnull": True})
    unused.delete()


class IdentityExport:
    """
    Collects the identities the exported applications act as, so that they're
    exported once, beside the applications, and the applications only hold a key.
    """

    def __init__(self) -> None:
        self._sources: dict[str, User | IdentityDefinition] = {}
        self._used_by: dict[str, set[int]] = defaultdict(set)

    def key_for(
        self, source: User | IdentityDefinition, application: Application
    ) -> str:
        """
        Records that the application acts as an identity, or waits for one.

        :param source: The identity, or the definition of one that doesn't exist yet.
        :param application: The exported application that refers to it.
        :return: The key the application refers to it by in the export.
        """

        # Not its id, which is a local reference. An import replaces the key.
        kind = "definition" if isinstance(source, IdentityDefinition) else "identity"
        key = salted_hmac(f"exported-{kind}", str(source.id)).hexdigest()
        self._sources[key] = source
        self._used_by[key].add(application.id)
        return key

    def serialize(
        self, exported_by: AbstractUser | None, application_ids: list[int]
    ) -> dict[str, Any] | None:
        """
        :param exported_by: The user who exports, if any. The roles they may not
            read are left out.
        :param application_ids: The exported applications. Roles on others are left
            out.
        :return: The part of the export that holds the identities, or None when the
            applications refer to none.
        """

        identities = []
        for key, source in self._sources.items():
            if isinstance(source, IdentityDefinition):
                name, email = source.name, source.source_email
                roles = self._definition_roles(source, exported_by)
            else:
                name, email = source.first_name, source.email
                roles = identity_extension_type_registry.get_application_roles(
                    source, exported_by
                )
            identities.append(
                {
                    "key": key,
                    "name": name,
                    "email": email,
                    "roles": None
                    if roles is None
                    else [
                        {
                            "scope_type": APPLICATION_SCOPE,
                            "scope_id": application_id,
                            "role": role_uid,
                        }
                        for application_id, role_uid in roles
                        if application_id in application_ids
                    ],
                    "used_by": sorted(self._used_by[key]),
                }
            )
        return {IDENTITIES: identities} if identities else None

    @staticmethod
    def _definition_roles(
        definition: IdentityDefinition, exported_by: AbstractUser | None
    ) -> list | None:
        if definition.roles is None:
            return None
        roles = [(role["scope_id"], role["role"]) for role in definition.roles]
        if exported_by is None:
            return roles
        return identity_extension_type_registry.filter_readable_application_roles(
            roles, exported_by, definition.workspace
        )


class IdentityImport:
    """
    Brings the identities of an export or a template into a workspace, around the
    import of its applications.

    Before the applications, every identity one of them refers to becomes a
    definition, and the identity itself when the importing user may create it. It
    has no access yet, and exists first so that the imported data that refers to it
    resolves to it. After the applications, it gets its roles on them, and the
    applications that wait for it are made to act as it.

    A definition whose identity wasn't created stays, and its applications wait.
    A failure to create an identity never fails the import.
    """

    def __init__(
        self,
        workspace: Workspace,
        workspace_objects: Any,
        user: AbstractUser | None,
        import_export_config: ImportExportConfig,
    ) -> None:
        """
        :param workspace: The workspace the applications are imported into.
        :param workspace_objects: The part of the file that holds the identities.
            Untrusted: what isn't understood is left out.
        :param user: The user who imports, or None when nobody does, as for the
            content of a template. Without one no identity is created.
        :param import_export_config: How the applications are imported.
        """

        self.workspace = workspace
        self.user = user
        self.import_export_config = import_export_config
        self._entries = self._parse(workspace_objects)
        self._definitions: list[IdentityDefinition] = []
        self._identities: dict[int, User] = {}

    @staticmethod
    def _parse(workspace_objects: Any) -> list[dict]:
        if not isinstance(workspace_objects, dict):
            return []
        serialized = workspace_objects.get(IDENTITIES)
        entries, keys = [], set()
        for identity in serialized if isinstance(serialized, list) else []:
            if not isinstance(identity, dict):
                continue
            key, name = identity.get("key"), identity.get("name")
            if not (isinstance(key, str) and key and key not in keys):
                continue
            if not (isinstance(name, str) and name.strip()):
                continue
            keys.add(key)
            email, roles = identity.get("email"), identity.get("roles")
            used_by = identity.get("used_by")
            entries.append(
                {
                    "key": key,
                    "name": name.strip()[:150],
                    # Only an address no person can have is a key for an identity.
                    "email": email
                    if isinstance(email, str)
                    and email.endswith(f"@{IDENTITY_EMAIL_DOMAIN}")
                    else None,
                    "roles": None
                    if roles is None
                    else [
                        role
                        for role in (roles if isinstance(roles, list) else [])
                        if isinstance(role, dict)
                        and role.get("scope_type") == APPLICATION_SCOPE
                        and type(role.get("scope_id")) is int
                        and isinstance(role.get("role"), str)
                    ],
                    "used_by": {
                        application_id
                        for application_id in (
                            used_by if isinstance(used_by, list) else []
                        )
                        if type(application_id) is int
                    },
                }
            )
        return entries

    def _can_create(self) -> bool:
        from baserow.core.identities.service import IdentityService

        return (
            self.user is not None
            # The content of a template is stored, not used: it holds no accounts.
            and not self.import_export_config.is_template_storage
            and IdentityService().can_create_scoped_identity(self.user, self.workspace)
        )

    def before_applications(
        self, id_mapping: dict, applications: list[tuple[int, str]]
    ) -> None:
        """
        Creates the definitions, and the identities the user may create.

        :param id_mapping: The export-to-import id map, filled in.
        :param applications: The exported id and the type of every application that
            is about to be imported.
        """

        definitions = id_mapping.setdefault(DEFINITIONS_MAPPING, {})
        emails = id_mapping.setdefault(EMAILS_MAPPING, {})
        if not self._entries:
            return
        types = dict(applications)
        can_create = self._can_create()
        names = (
            set(
                IdentityHandler()
                .get_queryset(self.workspace)
                .values_list("first_name", flat=True)
            )
            if can_create
            else set()
        )
        # An application acts as one identity at most, so a file can't make more
        # identities than it has applications that act as one.
        limit = sum(
            application_type_registry.get(type_name).binds_identities
            for type_name in types.values()
        )
        for entry in self._entries:
            if len(self._definitions) >= limit:
                break
            consumer_types = {
                application_type_registry.get(types[application_id])
                for application_id in entry["used_by"]
                if application_id in types
            }
            # Nothing that is imported acts as it.
            if not consumer_types:
                continue
            definition = IdentityDefinition.objects.create(
                workspace=self.workspace,
                name=entry["name"],
                source_email=entry["email"],
                # By exported ids, until the applications exist.
                roles=entry["roles"],
            )
            definitions[entry["key"]] = definition
            self._definitions.append(definition)
            if not can_create or not any(
                consumer_type.can_bind_imported_identities(self.user, self.workspace)
                for consumer_type in consumer_types
            ):
                continue
            identity = self._create(definition, names)
            if identity is None:
                continue
            names.add(identity.first_name)
            self._identities[definition.id] = identity
            if definition.source_email:
                emails[definition.source_email] = identity

    def _create(self, definition: IdentityDefinition, names: set[str]) -> User | None:
        from baserow.core.action.registries import action_type_registry
        from baserow.core.identities.actions import CreateScopedIdentityActionType

        # Identity names reach emails, so they get the check of the identities API.
        try:
            no_url_validation(definition.name)
        except ValidationError:
            logger.warning(
                "Not creating the imported identity of definition {}: its name "
                "can't be the name of an identity.",
                definition.id,
            )
            return None
        try:
            with transaction.atomic():
                return action_type_registry.get_by_type(
                    CreateScopedIdentityActionType
                ).do(
                    self.user,
                    self.workspace,
                    name=find_unused_name([definition.name], names, max_length=150),
                    applications=[],
                    can_change_data=False,
                )
        except SoftTimeLimitExceeded:
            raise
        except Exception as error:
            self._report(definition, error)
            return None

    @staticmethod
    def _report(definition: IdentityDefinition, error: Exception) -> None:
        if isinstance(error, (PermissionException, IdentityCannotBeScoped)):
            logger.warning(
                "Not creating the imported identity of definition {}: {}",
                definition.id,
                repr(error),
            )
            return
        logger.exception(
            "Could not create the imported identity of definition {}.", definition.id
        )
        exception_capturer(error)

    def after_applications(
        self, id_mapping: dict, applications: list[Application]
    ) -> None:
        """
        Gives the created identities their roles on the imported applications, and
        makes the applications that wait for them act as them.

        :param id_mapping: The export-to-import id map.
        :param applications: The imported applications.
        """

        if not self._definitions:
            return
        imported_ids = id_mapping.get("applications") or {}
        for definition in self._definitions:
            if definition.roles is not None:
                # Roles on things outside this import are dropped.
                definition.roles = [
                    {**role, "scope_id": imported_ids[role["scope_id"]]}
                    for role in definition.roles
                    if role["scope_id"] in imported_ids
                ]
                definition.save(update_fields=["roles"])
        by_type = defaultdict(list)
        for application in applications:
            by_type[application_type_registry.get_by_model(application)].append(
                application
            )
        for definition in self._definitions:
            identity = self._identities.get(definition.id)
            if identity is not None and not self._scope_and_bind(
                definition, identity, by_type
            ):
                self._remove(id_mapping, definition, identity)
        delete_unused_identity_definitions(
            [definition.id for definition in self._definitions]
        )

    def _scope_and_bind(
        self, definition: IdentityDefinition, identity: User, by_type: dict
    ) -> bool:
        """
        :return: Whether an imported application acts as the identity now.
        """

        from baserow.core.identities.service import IdentityService

        needs = [
            application_type.imported_identity_changes_data(definition, applications)
            for application_type, applications in by_type.items()
        ]
        try:
            with transaction.atomic():
                IdentityService().scope_identity(
                    self.user,
                    identity,
                    # Not the ones that act as an identity, so that an identity
                    # can't change what it, or another one, is allowed to do.
                    [
                        application
                        for application_type, applications in by_type.items()
                        if not application_type.binds_identities
                        for application in applications
                    ],
                    can_change_data=any(needs),
                    roles=None
                    if definition.roles is None
                    else [
                        (role["scope_id"], role["role"]) for role in definition.roles
                    ],
                )
                # A list, so that every type binds.
                return any(
                    [
                        application_type.bind_imported_identity(
                            self.user, definition, identity, applications
                        )
                        for application_type, applications in by_type.items()
                    ]
                )
        except SoftTimeLimitExceeded:
            raise
        except Exception as error:
            self._report(definition, error)
            return False

    def discard(self, id_mapping: dict) -> None:
        """
        Deletes the identities and the definitions this import created, when it
        failed and has no transaction to roll them back with.

        :param id_mapping: The export-to-import id map.
        """

        for definition in self._definitions:
            identity = self._identities.pop(definition.id, None)
            if identity is not None:
                self._remove(id_mapping, definition, identity)
        IdentityDefinition.objects.filter(
            id__in=[definition.id for definition in self._definitions]
        ).delete()
        self._definitions = []

    def _remove(
        self, id_mapping: dict, definition: IdentityDefinition, identity: User
    ) -> None:
        """
        Deletes an identity this import created that nothing acts as, so that it
        isn't left in the workspace, and records it like its creation. What the
        imported data attributed to it is left as after any deleted identity.
        """

        from baserow.core.action.registries import action_type_registry
        from baserow.core.identities.actions import DeleteIdentityActionType
        from baserow.core.identities.signals import identity_deleted
        from baserow.core.trash.handler import TrashHandler

        if definition.source_email:
            id_mapping[EMAILS_MAPPING].pop(definition.source_email, None)
        deleted = action_type_registry.get_by_type(DeleteIdentityActionType)
        deleted.register_action(
            user=self.user,
            params=deleted.Params(
                self.workspace.id,
                self.workspace.name,
                identity.id,
                identity.first_name,
            ),
            scope=deleted.scope(self.workspace.id),
            workspace=self.workspace,
        )
        identity_deleted.send(self, user=self.user, identity=identity)
        TrashHandler.permanently_delete(identity.profile)
