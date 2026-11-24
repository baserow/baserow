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
WORKSPACE_SCOPE = "workspace"
APPLICATION_SCOPE = "application"
# Written for an application whose roles can't be exported, so that the role on
# the workspace isn't given on it instead.
NO_ACCESS_ROLE_UID = "NO_ACCESS"
# The import's maps, kept in the `id_mapping` the applications are imported with.
IDENTITIES_MAPPING = "identities"
DEFINITIONS_MAPPING = "identity_definitions"
EMAILS_MAPPING = "identity_emails"
IMPORTER_MAPPING = "identity_importer"


def imported_identity(id_mapping: dict, key: Any) -> User | None:
    """
    :param id_mapping: The export-to-import id map.
    :param key: The key an exported application refers to an identity by.
    :return: The identity this import created for the key, if it did.
    """

    return (id_mapping.get(IDENTITIES_MAPPING) or {}).get(_usable(key))


def imported_identity_definition(
    id_mapping: dict, key: Any
) -> IdentityDefinition | None:
    """
    :param id_mapping: The export-to-import id map.
    :param key: The key an exported application refers to an identity by.
    :return: The definition to wait for, when the identity of the key wasn't
        created.
    """

    return (id_mapping.get(DEFINITIONS_MAPPING) or {}).get(_usable(key))


def identity_importer(id_mapping: dict) -> AbstractUser | None:
    """
    :param id_mapping: The export-to-import id map.
    :return: The user the identities of this import were created on behalf of.
    """

    return id_mapping.get(IMPORTER_MAPPING)


def imported_identity_emails(id_mapping: dict) -> dict[str, User]:
    """
    :param id_mapping: The export-to-import id map.
    :return: The identities this import created, by the address the exported data
        refers to them by.
    """

    return id_mapping.get(EMAILS_MAPPING) or {}


def _usable(key: Any) -> str | None:
    return key if isinstance(key, str) and key else None


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
    Collects the identities the exported applications refer to, so that they're
    exported once, beside the applications, and the applications only hold a key.
    """

    def __init__(self) -> None:
        self._sources: dict[str, User | IdentityDefinition] = {}

    def key_for(self, source: User | IdentityDefinition) -> str:
        """
        Records that an exported application refers to an identity, or waits for
        one.

        :param source: The identity, or the definition of one that doesn't exist yet.
        :return: The key the application refers to it by in the export.
        """

        # Not its id, which is a local reference. An import replaces the key.
        kind = "definition" if isinstance(source, IdentityDefinition) else "identity"
        key = salted_hmac(f"exported-{kind}", str(source.id)).hexdigest()
        self._sources[key] = source
        return key

    def serialize(
        self, exported_by: AbstractUser | None, application_ids: list[int]
    ) -> dict[str, Any] | None:
        """
        :param exported_by: The user who exports, if any. An application whose
            roles they may not read is exported as one the identity can't access.
        :param application_ids: The exported applications. Roles on others are left
            out.
        :return: The part of the export that holds the identities, or None when the
            applications refer to none.
        """

        identities = []
        for key, source in self._sources.items():
            if isinstance(source, IdentityDefinition):
                name, email, workspace = (
                    source.name,
                    source.source_email,
                    source.workspace,
                )
                workspace_role, application_roles = _split_roles(source.roles or [])
            else:
                name, email = source.first_name, source.email
                workspace = IdentityHandler.get_workspace(source)
                workspace_role = IdentityHandler.get_role_uid(source)
                application_roles = dict(
                    identity_extension_type_registry.get_application_roles(source) or []
                )
            identities.append(
                {
                    "key": key,
                    "name": name,
                    "email": email,
                    "roles": self._roles(
                        workspace_role,
                        application_roles,
                        workspace,
                        exported_by,
                        application_ids,
                    ),
                }
            )
        return {IDENTITIES: identities} if identities else None

    @staticmethod
    def _roles(
        workspace_role: str | None,
        application_roles: dict[int, str],
        workspace: Workspace,
        exported_by: AbstractUser | None,
        application_ids: list[int],
    ) -> list[dict]:
        """
        :return: The role on the workspace, and the role on each exported
            application that has its own.
        """

        readable = set(application_ids)
        if exported_by is not None:
            readable = {
                application_id
                for application_id, _ in (
                    identity_extension_type_registry.filter_readable_application_roles(
                        [(application_id, None) for application_id in application_ids],
                        exported_by,
                        workspace,
                    )
                )
            }
        roles = []
        if workspace_role:
            roles.append({"scope_type": WORKSPACE_SCOPE, "role": workspace_role})
        for application_id in sorted(application_ids):
            if application_id not in readable:
                # It may have a narrower role there than on the workspace.
                role = NO_ACCESS_ROLE_UID
            elif application_id in application_roles:
                role = application_roles[application_id]
            else:
                continue
            roles.append(
                {
                    "scope_type": APPLICATION_SCOPE,
                    "scope_id": application_id,
                    "role": role,
                }
            )
        return roles


def _split_roles(roles: list[dict]) -> tuple[str | None, dict[int, str]]:
    """
    :param roles: The roles of an exported identity, as parsed by an import.
    :return: Its role on the workspace, and its roles by application id.
    """

    workspace_role = next(
        (role["role"] for role in roles if role["scope_type"] == WORKSPACE_SCOPE),
        None,
    )
    return workspace_role, {
        role["scope_id"]: role["role"]
        for role in roles
        if role["scope_type"] == APPLICATION_SCOPE
    }


class IdentityImport:
    """
    Brings the identities of an export or a template into a workspace, around the
    import of its applications.

    Before the applications, every identity one of them refers to is created,
    when the importing user may. It has no access yet, and exists first so that
    the imported applications and their data resolve to it like any other
    reference. An identity that isn't created becomes a definition, which the
    applications wait for. After the applications, each created identity gets its
    roles on them.

    A failure to create an identity or to give it its roles never fails the
    import.
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
        # The created identities, with the roles they came with.
        self._identities: list[tuple[User, list[dict]]] = []
        # The exported ids of the applications that refer to an identity.
        self._referring: set[int] = set()

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
            if not (isinstance(name, str) and name.strip() and "\x00" not in name):
                continue
            keys.add(key)
            email = identity.get("email")
            # Only an address no person can have is a key for an identity.
            if not (
                isinstance(email, str)
                and len(email) <= 254
                and "\x00" not in email
                and email.endswith(f"@{IDENTITY_EMAIL_DOMAIN}")
            ):
                email = None
            entries.append(
                {
                    "key": key,
                    "name": name.strip()[:150],
                    "email": email,
                    "roles": IdentityImport._parse_roles(identity.get("roles")),
                }
            )
        return entries

    @staticmethod
    def _parse_roles(serialized: Any) -> list[dict]:
        roles, has_workspace_role = [], False
        for role in serialized if isinstance(serialized, list) else []:
            if not (isinstance(role, dict) and isinstance(role.get("role"), str)):
                continue
            if role.get("scope_type") == WORKSPACE_SCOPE and not has_workspace_role:
                has_workspace_role = True
                roles.append({"scope_type": WORKSPACE_SCOPE, "role": role["role"]})
            elif (
                role.get("scope_type") == APPLICATION_SCOPE
                and type(role.get("scope_id")) is int
            ):
                roles.append(
                    {
                        "scope_type": APPLICATION_SCOPE,
                        "scope_id": role["scope_id"],
                        "role": role["role"],
                    }
                )
        return roles

    def _can_create(self) -> bool:
        from baserow.core.identities.service import IdentityService

        return (
            self.user is not None
            # The content of a template is stored, not used: it holds no accounts.
            and not self.import_export_config.is_template_storage
            and IdentityService().can_create_scoped_identity(self.user, self.workspace)
        )

    def before_applications(
        self, id_mapping: dict, serialized_applications: list[dict]
    ) -> None:
        """
        Creates the identities the applications refer to, or their definitions
        when the user may not create them.

        :param id_mapping: The export-to-import id map, filled in.
        :param serialized_applications: The applications that are about to be
            imported.
        """

        identities = id_mapping.setdefault(IDENTITIES_MAPPING, {})
        definitions = id_mapping.setdefault(DEFINITIONS_MAPPING, {})
        emails = id_mapping.setdefault(EMAILS_MAPPING, {})
        id_mapping[IMPORTER_MAPPING] = self.user
        if not self._entries:
            return
        referred = set()
        for application in serialized_applications:
            keys = application_type_registry.get(
                application["type"]
            ).get_imported_identity_keys(application, self.user)
            if keys:
                referred.update(keys)
                self._referring.add(application.get("id"))
        entries = [entry for entry in self._entries if entry["key"] in referred]
        if not entries:
            return
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
        source_emails = set()
        for entry in entries:
            # What refers to an address goes to the first identity that had it.
            email = None if entry["email"] in source_emails else entry["email"]
            source_emails.add(email)
            identity = self._create(entry, names) if can_create else None
            if identity is None:
                definition = IdentityDefinition.objects.create(
                    workspace=self.workspace,
                    name=entry["name"],
                    source_email=email,
                    # By exported ids, until the applications exist.
                    roles=entry["roles"],
                )
                definitions[entry["key"]] = definition
                self._definitions.append(definition)
                continue
            names.add(identity.first_name)
            identities[entry["key"]] = identity
            self._identities.append((identity, entry["roles"]))
            if email:
                emails[email] = identity

    def _create(self, entry: dict, names: set[str]) -> User | None:
        from baserow.core.action.registries import action_type_registry
        from baserow.core.identities.actions import CreateScopedIdentityActionType

        # Identity names reach emails, so they get the check of the identities API.
        try:
            no_url_validation(entry["name"])
        except ValidationError:
            logger.warning(
                "Not creating the imported identity {}: its name can't be the "
                "name of an identity.",
                entry["key"],
            )
            return None
        try:
            with transaction.atomic():
                return action_type_registry.get_by_type(
                    CreateScopedIdentityActionType
                ).do(
                    self.user,
                    self.workspace,
                    name=find_unused_name([entry["name"]], names, max_length=150),
                )
        except SoftTimeLimitExceeded:
            raise
        except Exception as error:
            self._report("create", entry["key"], error)
            return None

    @staticmethod
    def _report(step: str, subject: Any, error: Exception) -> None:
        if isinstance(error, (PermissionException, IdentityCannotBeScoped)):
            logger.warning(
                "Could not {} the imported identity {}: {}", step, subject, repr(error)
            )
            return
        logger.exception("Could not {} the imported identity {}.", step, subject)
        exception_capturer(error)

    def after_applications(
        self, id_mapping: dict, applications: list[Application]
    ) -> None:
        """
        Gives the created identities their roles on the imported applications.

        :param id_mapping: The export-to-import id map.
        :param applications: The imported applications.
        """

        imported_ids = id_mapping.get("applications") or {}
        for definition in self._definitions:
            # Roles on things outside this import are dropped.
            definition.roles = [
                {**role, "scope_id": imported_ids[role["scope_id"]]}
                if role["scope_type"] == APPLICATION_SCOPE
                else role
                for role in definition.roles
                if role["scope_type"] != APPLICATION_SCOPE
                or role["scope_id"] in imported_ids
            ]
            definition.save(update_fields=["roles"])
        if not self._identities:
            return
        # Not the ones that refer to an identity, so that an identity can't change
        # what it, or another one, is allowed to do.
        referring = {
            imported_ids[application_id]
            for application_id in self._referring
            if application_id in imported_ids
        }
        exported_ids = {new_id: old_id for old_id, new_id in imported_ids.items()}
        scoped = [
            application
            for application in applications
            if application.id not in referring
        ]
        for identity, roles in self._identities:
            workspace_role, application_roles = _split_roles(roles)
            self._scope(
                identity,
                scoped,
                [
                    (
                        application.id,
                        # Its own role on the application, or else the one it had
                        # on the whole workspace.
                        application_roles.get(
                            exported_ids.get(application.id), workspace_role
                        ),
                    )
                    for application in scoped
                ],
            )

    def _scope(
        self,
        identity: User,
        applications: list[Application],
        roles: list[tuple[int, str | None]],
    ) -> None:
        from baserow.core.identities.service import IdentityService

        try:
            with transaction.atomic():
                IdentityService().scope_identity(
                    self.user,
                    identity,
                    applications,
                    [(application_id, role) for application_id, role in roles if role],
                )
        except SoftTimeLimitExceeded:
            raise
        except Exception as error:
            # It keeps no access, which whoever manages identities can change.
            self._report("give roles to", identity.id, error)

    def discard(self, id_mapping: dict) -> None:
        """
        Trashes the identities this import created, when it failed and has no
        transaction to roll them back with. Like the applications it did import,
        which are trashed too, they can be restored. The definitions are kept for
        the trashed applications that wait for them.

        :param id_mapping: The export-to-import id map.
        """

        from baserow.core.action.registries import action_type_registry
        from baserow.core.identities.actions import DeleteIdentityActionType
        from baserow.core.identities.signals import identity_deleted

        deleted = action_type_registry.get_by_type(DeleteIdentityActionType)
        for identity, _ in self._identities:
            IdentityHandler().delete_identity(self.user, identity)
            # Recorded like its creation.
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
        self._identities = []
        for mapping in (IDENTITIES_MAPPING, EMAILS_MAPPING):
            id_mapping.get(mapping, {}).clear()
        delete_unused_identity_definitions(
            [definition.id for definition in self._definitions]
        )
