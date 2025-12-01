import abc
import dataclasses
from collections import defaultdict
from functools import cached_property
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, TypeVar, Union
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db.models import Q, QuerySet
from django.db.transaction import Atomic

from rest_framework.serializers import Serializer

from baserow.contrib.database.constants import IMPORT_SERIALIZED_IMPORTING
from baserow.core.auth_provider.registries import AuthenticationProviderTypeRegistry
from baserow.core.exceptions import SubjectTypeNotExist
from baserow.core.storage import ExportZipFile
from baserow.core.utils import ChildProgressBuilder

from .exceptions import (
    ApplicationTypeAlreadyRegistered,
    ApplicationTypeDoesNotExist,
    ObjectScopeTypeAlreadyRegistered,
    ObjectScopeTypeDoesNotExist,
    OperationTypeAlreadyRegistered,
    OperationTypeDoesNotExist,
    PermissionException,
    PermissionManagerTypeAlreadyRegistered,
    PermissionManagerTypeDoesNotExist,
)
from .export_serialized import CoreExportSerializedStructure
from .registry import (
    APIUrlsInstanceMixin,
    APIUrlsRegistryMixin,
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    PublicCustomFieldsInstanceMixin,
    Registry,
)
from .types import (
    Actor,
    ContextObject,
    PermissionCheck,
    ScopeObject,
    SerializationProcessorScope,
    Subject,
)

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import (
        Application,
        Template,
        Workspace,
        WorkspaceInvitation,
    )


@dataclasses.dataclass
class ImportExportConfig:
    """
    When true the export/import will also transfer any permission data.

    For example when exporting to JSON we don't want to include RBAC data as we would
    also need to export all the subjects, so setting this to False will exclude
    RBAC roles from the export.
    """

    include_permission_data: bool

    reduce_disk_space_usage: bool = False
    """
    Whether or not the import/export should attempt to save disk space by excluding
    certain pieces of optional data or processes that could instead be done later or
    not used at all.

    For example, this configures the database when True to not create/populate
    tsvector full text search columns as they can also be lazy loaded after the import
    when the user opens a view.
    """

    workspace_for_user_references: "Workspace" = None
    """
    Determines an alternative workspace to search for user references
    during imports.
    """

    is_duplicate: bool = False
    """
    Indicates whether the import export operation is duplicating an existing object.
    The data then doesn't leave the instance.
    """

    is_publishing: bool = False
    """
    Indicates whether or not we are currently publishing. This class is used
    to pass context to actions like publishing, duplicating, etc. In some cases,
    it is necessary to know whether the action is specifically publishing.
    """

    only_structure: bool = False
    """
    Whether or not the export should include the user data
    """

    exclude_sensitive_data: bool = True
    """
    When True, during an export any sensitive fields defined in the
    `sensitive_fields` list will have their serialized values set to None. This
    ensures that sensitive data are excluded from the exported workspace file.
    """


class Plugin(APIUrlsInstanceMixin, Instance):
    """
    This abstract class represents a custom plugin that can be added to the plugin
    registry. It must be extended so customisation can be done. Each plugin can register
    urls to the root and to the api.

    The added API urls will be available under the namespace 'api'. So if a url
    with name 'example' is returned by the method it will available under
    reverse('api:example').

    Example:
        from django.http import HttpResponse
        from baserow.core.registries import Plugin, plugin_registry

        def page_1(request):
            return HttpResponse('Page 2')

        class ExamplePlugin(Plugin):
            type = 'a-unique-type-name'

            # Will be added to the root.
            def get_urls(self):
                return [
                    url(r'^page-1$', page_1, name='page_1')
                ]

            # Will be added to the API.
            def get_api_urls(self):
                return [
                    path('application-type/', include(api_urls, namespace=self.type)),
                ]

        plugin_registry.register(ExamplePlugin())
    """

    def get_urls(self):
        """
        If needed root urls related to the plugin can be added here.

        Example:

            def get_urls(self):
                from . import api_urls

                return [
                    path('some-url/', include(api_urls, namespace=self.type)),
                ]

            # api_urls.py
            from django.urls import re_path

            urlpatterns = [
                url(r'some-view^$', SomeView.as_view(), name='some_view'),
            ]

        :return: A list containing the urls.
        :rtype: list
        """

        return []

    def user_created(
        self,
        user: "AbstractUser",
        workspace: "Workspace" = None,
        workspace_invitation: "WorkspaceInvitation" = None,
        template: "Template" = None,
    ):
        """
        A hook that is called after a new user has been created. This is the place to
        create some data the user can start with. A workspace will most often be
        created, but won't be if the account has `allow_global_workspace_creation`
        set to `False`.

        :param user: The newly created user.
        :type user: User
        :param workspace: The newly created workspace for the user.
        :type workspace: Workspace or None
        :param workspace_invitation: Is provided if the user has signed up using a valid
            workspace invitation token.
        :type workspace_invitation: WorkspaceInvitation or None
        :param template: The template that is installed right after creating the
            account. Is `None` if the template was not created.
        :type template: Template or None
        """

    def create_initial_workspace(
        self,
        user: "AbstractUser",
        workspace: "Workspace" = None,
    ):
        """
        A hook that is called after a new initial workspace is created. This is the
        place to create some data the user can start with.

        :param user: The user that requested the new workspace.
        :param workspace: The newly created workspace where the additional data must
            be added to.
        """

    def user_signed_in(self, user):
        """
        A hook that is called after an existing user has signed in.

        :param user: The user that just signed in.
        :type user: User
        """

    def enhance_workspace_queryset(
        self, queryset: QuerySet["Workspace"]
    ) -> QuerySet["Workspace"]:
        """
        Optimizes the queryset by adding select and prefetch related statements.
        This reduces queries and improves performance when accessing workspace-related
        models in plugin views or methods.

        :param queryset: The queryset to optimize.
        :return: The optimized queryset.
        """

        return queryset


class PluginRegistry(APIUrlsRegistryMixin, Registry[Plugin]):
    """
    With the plugin registry it is possible to register new plugins. A plugin is an
    abstraction made specifically for Baserow. It allows a plugin developer to
    register extra api and root urls.
    """

    name = "plugin"

    @property
    def urls(self):
        """
        Returns a list of all the urls that are in the registered instances. They
        are going to be added to the root url config.

        :return: The urls of the registered instances.
        :rtype: list
        """

        urls = []
        for types in self.registry.values():
            urls += types.get_urls()
        return urls


class ApplicationType(
    APIUrlsInstanceMixin,
    ModelInstanceMixin["Application"],
    PublicCustomFieldsInstanceMixin,
    CustomFieldsInstanceMixin,
    Instance,
):
    """
    This abstract class represents a custom application that can be added to the
    application registry. It must be extended so customisation can be done. Each
    application will have his own model that must extend the Application model, this is
    needed so that the user can set custom settings per application instance they have
    created.

    The added API urls will be available under the namespace 'api'. So if a url
    with name 'example' is returned by the method it will available under
    reverse('api:example').

    Example:
        from baserow.core.models import Application
        from baserow.core.registries import ApplicationType, application_type_registry

        class ExampleApplicationModel(Application):
            pass

        class ExampleApplication(ApplicationType):
            type = 'a-unique-type-name'
            model_class = ExampleApplicationModel

            def get_api_urls(self):
                return [
                    path('application-type/', include(api_urls, namespace=self.type)),
                ]

        application_type_registry.register(ExampleApplication())

    """

    instance_serializer_class = None
    """This serializer that is used to serialize the instance model."""

    supports_actions = True

    supports_snapshots = True

    supports_integrations = False

    supports_user_sources = False

    # The order in which this application type is imported in
    # `import_applications_to_workspace`. By default, the priority is `0`, the lowest
    # value. If this property is not overridden, then the instance is imported last.
    import_application_priority = 0

    def prepare_value_for_db(self, values: dict, instance: "Application | None" = None):
        """
        This function allows you to hook into the moment an application is created or
        updated. If the application is updated, `instance` of the current application
        will be defined.

        :param values: The values that are being updated
        :param instance: (optional) The existing instance that is being updated
        """

        return values

    def after_create(self, instance: "Application", values: Dict):
        """
        This hook is called right after the application has been created.

        :param instance: The created application instance.
        :param values: The values that were passed when creating the field
            instance.
        """

    def after_update(
        self,
        instance: "Application",
        values: Dict,
    ):
        """
        This hook is called right after the application has been updated.

        :param instance: The updated application instance.
        :param values: The values that were passed when updating the instance.
        """

    def pre_delete(self, application):
        """
        A hook that is called before the application instance is deleted.

        :param application: The application model instance that needs to be deleted.
        :type application: Application
        """

    def export_safe_transaction_context(self, application: "Application") -> Atomic:
        """
        Should return an Atomic context (such as transaction.atomic or
        baserow.contrib.database.db.atomic.read_repeatable_single_database_atomic_transaction)
        which can be used to safely run a database transaction to export an application
        of this type.

        :param application: The application that we are about to export.
        :return: An Atomic context object that will be used to open a transaction safely
            to export an application of this type.
        """

        raise NotImplementedError(
            "Must be implemented by the specific application type"
        )

    def create_application(
        self, user, workspace: "Workspace", init_with_data: bool = False, **kwargs
    ) -> "Application":
        """
        Creates a new application instance of this type and returns it.

        :param user: The user that is creating the application.
        :param workspace: The workspace that the application will be created in.
        :param init_with_data: Whether the application should be created with some
            initial data. Defaults to False.
        :param kwargs: Additional parameters to pass to the application creation,
            these values have already been validated by the view and are allowed.
        :return: The newly created application instance.
        """

        model = self.model_class
        last_order = model.get_last_order(workspace)

        instance = model.objects.create(workspace=workspace, order=last_order, **kwargs)
        if init_with_data:
            self.init_application(user, instance)
        return instance

    def init_application(self, user, application: "Application") -> None:
        """
        This method can be called when the application is created to
        initialize it with some default data.

        :param user: The user that is creating the application.
        :param application: The application to initialize with data.
        """

    def export_serialized_structure_with_registry(
        self,
        workspace: "Workspace",
        scope,
        exported_structure: dict,
        import_export_config: ImportExportConfig,
    ) -> dict:
        """
        Given a serialized dictionary generated by `export_serialized`, this method
        will iterate over `serialization_processor_registry` and include any new data
        that needs to be added to the serialized structure.
        """

        for serialized_structure in serialization_processor_registry.get_all():
            data = serialized_structure.export_serialized(
                workspace, scope, import_export_config
            )
            if data is not None:
                exported_structure.update(**data)
        return exported_structure

    def import_serialized_structure_with_registry(
        self,
        id_mapping: Dict[str, Any],
        scope,
        serialized_scope: dict,
        import_export_config: ImportExportConfig,
        workspace: Optional["Workspace"] = None,
    ) -> None:
        """
        Given a serialized dictionary passed into `imported_serialized`, this method
        will iterate over `serialization_processor_registry` and import any data that
        `serialization_processor_registry` wants to include.
        """

        source_workspace = workspace
        from baserow.core.models import Workspace

        if not source_workspace:
            source_workspace = Workspace.objects.get(
                pk=id_mapping["import_workspace_id"]
            )

        for serialized_structure in serialization_processor_registry.get_all():
            serialized_structure.import_serialized(
                source_workspace, scope, serialized_scope, import_export_config
            )

    def export_serialized(
        self,
        application: "Application",
        import_export_config: ImportExportConfig,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ):
        """
        Exports the application to a serialized dict that can be imported by the
        `import_serialized` method. The dict is JSON serializable.

        :param application: The application that must be exported.
        :type application: Application
        :param files_zip: A zip file buffer where the files related to the template
            must be copied into.
        :type files_zip: ZipFile
        :param storage: The storage where the files can be loaded from.
        :type storage: Storage or None
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :return: The exported and serialized application.
        :rtype: dict
        """

        progress = ChildProgressBuilder.build(progress_builder, child_total=1)

        structure = CoreExportSerializedStructure.application(
            id=application.id,
            name=application.name,
            order=application.order,
            type=self.type,
        )
        # Annotate any `SerializationProcessorType` we have.
        structure = self.export_serialized_structure_with_registry(
            application.get_root(), application, structure, import_export_config
        )
        progress.increment()
        return structure

    def import_serialized(
        self,
        workspace: "Workspace",
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> "Application":
        """
        Imports the exported serialized application by the `export_serialized` as a new
        application to a workspace.

        :param workspace: The workspace that the application must be added to.
        :param serialized_values: The exported serialized values by the
            `export_serialized` method.
        :param id_mapping: The map of exported ids to newly created ids that must be
            updated when a new instance has been created.
        :param files_zip: A zip file buffer where files related to the template can
            be extracted from.
        :param storage: The storage where the files can be copied to.
        :param progress_builder: If provided will be used to build a child progress bar
            and report on this methods progress to the parent of the progress_builder.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :return: The newly created application.
        """

        if "import_workspace_id" not in id_mapping and workspace is not None:
            id_mapping["import_workspace_id"] = workspace.id

        if "applications" not in id_mapping:
            id_mapping["applications"] = {}

        # Narrow `serialized_values` down to just values relevant to
        # `Application` creation.
        serialized_application_values = (
            CoreExportSerializedStructure.filter_application_fields(serialized_values)
        )

        serialized_copy = serialized_application_values.copy()
        application_id = serialized_copy.pop("id")
        serialized_copy.pop("type")

        # If the Application originates from a Snapshot, pop it
        # off, we'll use it after the Application has been created.
        snapshot_from = serialized_copy.pop("snapshot_from", None)

        application = self.model_class.objects.create(
            workspace=workspace, **serialized_copy
        )

        # The Application comes from a Snapshot, set its
        # `snapshot_from` related manager. This ensures that
        # an Application with workspace=None can have a parent.
        if snapshot_from:
            application.snapshot_from.set([snapshot_from])

        id_mapping["applications"][application_id] = application.id

        progress = ChildProgressBuilder.build(progress_builder, child_total=1)
        progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        # Finally, now that everything has been created, loop over the
        # `serialization_processor_registry` registry and ensure extra
        # metadata is imported too.
        self.import_serialized_structure_with_registry(
            id_mapping,
            application,
            serialized_values,
            import_export_config,
            workspace,
        )

        return application

    def enhance_queryset(
        self, queryset: QuerySet["Application"]
    ) -> QuerySet["Application"]:
        """
        Enhances the queryset by adding additional select related and prefetch related
        statements to improve the performance of the queryset and to reduce the amount
        of queries that are executed when the queryset is evaluated and the objects are
        accessed or serialized.

        :param queryset: The queryset to enhance.
        :return: The enhanced queryset.
        """

        return queryset

    def enhance_and_filter_queryset(
        self,
        queryset: QuerySet["Application"],
        user: "AbstractUser",
        workspace: "Workspace",
    ) -> QuerySet["Application"]:
        """
        Same as `enhance_queryset` but also filters the queryset based on the user's
        permissions.

        :param queryset: The queryset to enhance and filter.
        :param user: The user that is trying to access the queryset.
        :param workspace: The workspace that the queryset is related to.
        """

        return queryset

    def get_application_urls(self, application: "Application") -> list[str]:
        """
        Returns the frontend urls of the application if any.
        """

        return []

    @classmethod
    def get_application_id_for_url(cls, url: str) -> int | None:
        """
        Given a URL, returns the application id related to this URL
        or None if None matches.

        :param url: the url to search the application_id for.
        """

        return None


ApplicationSubClassInstance = TypeVar(
    "ApplicationSubClassInstance", bound="Application"
)


class ApplicationTypeRegistry(
    APIUrlsRegistryMixin,
    ModelRegistryMixin[ApplicationSubClassInstance, ApplicationType],
    Registry[ApplicationType],
    CustomFieldsRegistryMixin,
):
    """
    With the application registry it is possible to register new applications. An
    application is an abstraction made specifically for Baserow. If added to the
    registry a user can create new instances of that application via the app and
    register api related urls.
    """

    name = "application"
    does_not_exist_exception_class = ApplicationTypeDoesNotExist
    already_registered_exception_class = ApplicationTypeAlreadyRegistered


class PermissionManagerType(abc.ABC, Instance):
    """
    A permission manager is responsible to permit or disallow a specific operation
    according to the given context.

    A permission manager is also responsible to generate the data sent to the
    frontend to make it check the permission.

    And finally, a permission manager can filter the list querysets
    to remove disallowed objects from this list.

    See each PermissionManager method and `CoreHandler` methods for more details.
    """

    # A list of subject types that are supported by this permission manager.
    supported_actor_types = []

    def actor_is_supported(self, actor: Actor):
        """
        Returns whether the actor given in parameter is handled by this manager type or
        not.
        """

        actor_type = subject_type_registry.get_by_model(actor)
        return actor_type.type in self.supported_actor_types

    def check_permissions(
        self,
        actor: Actor,
        operation_name: str,
        workspace: Optional["Workspace"] = None,
        context: Optional[Any] = None,
        include_trash: bool = False,
    ) -> Optional[bool]:
        """
        This method is a helper to check permission with this permission manager when
        you need to do only one check. It calls `.check_multiple_permissions` behind
        the scene.

        It:
            - returns `True` if the operation is permitted given the other parameters
            - raise a `PermissionException` exception if the operation is disallowed
            - return `None` if the pre-condition required by the permission manager
              are not met.

        :param actor: The actor who wants to execute the operation. Generally a `User`,
            but can be a `Token`.
        :param operation_name: The operation name the actor wants to execute.
        :param workspace: The optional workspace in which  the operation takes place.
        :param context: The optional object affected by the operation. For instance
            if you are updating a `Table` object, the context is this `Table` object.
        :param include_trash: If true then also checks if the given workspace has been
            trashed instead of raising a DoesNotExist exception.
        :raise PermissionException: If the operation is disallowed.
        :return: `True` if the operation is permitted, None if the permission manager
            can't decide.
        """

        check = PermissionCheck(actor, operation_name, context)
        result = self.check_multiple_permissions(
            [check],
            workspace,
            include_trash=include_trash,
        ).get(check, None)

        if isinstance(result, PermissionException):
            raise result

        return result

    @abc.abstractmethod
    def check_multiple_permissions(
        self,
        checks: List[PermissionCheck],
        workspace: "Workspace" = None,
        include_trash: bool = False,
    ) -> Dict[PermissionCheck, Union[bool, PermissionException]]:
        """
        This method is called each time multiple permissions are checked at once
        by the `CoreHandler().check_multiple_permissions()` method if the current
        permission manager is listed in the `settings.PERMISSION_MANAGERS` list.

        It should return a map (dict) with for each check as key, if the related
        triplet (actor, permission_name, scope) is allowed (True) or disallowed
        (A permission exception).
        If a check is omitted in the result, it means that the check is not supported
        by this permission manager.

        This method MUST be implemented by each permission manager type.

        :param checks: The list of check to do. Each check is a triplet of
            (actor, permission_name, scope).
        :param workspace: The optional workspace in which the operations take place.
        :param include_trash: If true then also checks if the given workspace has been
            trashed instead of raising a DoesNotExist exception.
        :return: A dictionary with one entry for each check of the parameter as key and
            whether the operation is allowed or not as value. Check entries can be
            omitted in the response dict if the check allowance can't be decided by this
            permission manager.
        """

        raise NotImplementedError(
            "Must be implemented by the specific application type"
        )

    def get_permissions_object(
        self, actor: Actor, workspace: Optional["Workspace"] = None
    ) -> Any:
        """
        This method should return the data necessary to easily check a permission from
        a client. This object can be used for instance from the frontend to hide or
        show UI element accordingly to the user permissions.
        The data set returned must contain all the necessary information to prevent and
        the client shouldn't have to get more data to decide.

        This method is called when the `CoreHandler().get_permissions()` is called,
        if the permission manager is listed in the `settings.PERMISSION_MANAGERS`.
        It can return `None` if this permission manager is not relevant for the given
        actor/workspace for some reason.

        By default this method returns None.

        :param actor: The actor whom we want to compute the permission object for.
        :param workspace: The optional workspace into which we want to compute the
            permission object.
        :return: The permission object or None.
        """

        return None

    def filter_queryset(
        self,
        actor: Actor,
        operation_name: str,
        queryset: QuerySet,
        workspace: Optional["Workspace"] = None,
    ) -> QuerySet:
        """
        This method allows a permission manager to filter a given queryset accordingly
        to the actor permissions in the specified context. The
        `CoreHandler().filter_queryset()` method calls each permission manager listed in
        `settings.PERMISSION_MANAGERS` to successively filter the given queryset.

        :param actor: The actor whom we want to filter the queryset for.
            Generally a `User` but can be a Token.
        :param operation_name: The operation name for which we want to filter the
            queryset for.
        :param queryset: The base queryset where the permission filter must be
            applied to.
        :param workspace: An optional workspace into which the operation takes place.
        :return: The queryset potentially filtered.
        """

    def get_roles(self) -> List:
        """
        Get all the roles available for your permissions system
        """

        return []


class PermissionManagerTypeRegistry(Registry[PermissionManagerType]):
    """
    This registry contains all the permission manager used to handle permissions in
    Baserow. A permission manager must then be listed in the
    `settings.PERMISSION_MANAGERS` variable to be used by the `CoreHandler` methods.
    """

    name = "permission_manager"

    does_not_exist_exception_class = PermissionManagerTypeDoesNotExist
    already_registered_exception_class = PermissionManagerTypeAlreadyRegistered


class ObjectScopeType(Instance, ModelInstanceMixin):
    """
    This type describe an object scope in Baserow. This is useful if you need to know
    the object hierarchy. This hierarchy is used by the permission system, for example,
    to determine if a context object is included by a given scope.
    It can also be used to list all context object of a scope included by another scope.

    An `ObjectScopeType` must be registered for each object that can be a scope or a
    context.
    """

    def get_parent_scope(self) -> Optional["ObjectScopeType"]:
        """
        Returns the parent scope of the current scope.

        :return: the parent `ObjectScopeType` or `None` if it's a root scope.
        """

        return None

    def get_parent_scopes(self) -> List["ObjectScopeType"]:
        """
        Returns the parent scope of the current scope.

        :return: the parent `ObjectScopeType` or `None` if it's a root scope.
        """

        parent_scope = self.get_parent_scope()
        if not parent_scope:
            return []

        return [parent_scope] + parent_scope.get_parent_scopes()

    def get_parents(self, context: ContextObject) -> List[ContextObject]:
        """
        Returns all ancestors of the given context which belongs to the current
        scope.

        :param context: The context object which we want the ancestors for. This object
            must belong to the current scope.
        :return: the list of parent objects if it's a root object.
        """

        parent = context.get_parent()

        if parent is None:
            return []

        parents = self.get_parent_scope().get_parents(parent)
        parents.append(parent)

        return parents

    def get_all_context_objects_in_scope(self, scope: ScopeObject) -> Iterable:
        """
        Returns the list of context object belonging to the current scope that are
        included in the scope object given in parameter.

        :param scope: The scope into which we want the context objects for.
        :return: An iterable containing the context objects for the given scope.
        """

        return self.get_objects_in_scopes([scope])[scope]

    def get_filter_for_scope_type(
        self, scope_type: "ObjectScopeType", scopes: List[Any]
    ) -> Q:
        """
        Returns the filter to apply to the queryset that selects all the context
        objects included in the given scopes.
        All the scopes must be members of the given scope type.

        :param scope_type: The scope type the scopes belongs to.
        :param scopes: The scopes objects we want the context object for.
        :return: A Q object that can be used in a filter operation.
        """

        raise NotImplementedError(
            f"Must be implemented by the specific type <{self.type}>"
        )

    def get_base_queryset(self, include_trash: bool = False) -> QuerySet:
        """
        :params include_trash: If true then also includes trashed objects in the
            queryset. Needed to verify if a user needs to be included in the recipient
            list of a deleted_* signal.
        Returns the base queryset for the objects of this scope
        """

        model_manager = self.model_class.objects
        if include_trash and hasattr(self.model_class, "objects_and_trash"):
            model_manager = self.model_class.objects_and_trash
        return model_manager.order_by().all()

    def get_enhanced_queryset(self, include_trash: bool = False) -> QuerySet:
        """
        :params include_trash: If true then also includes trashed objects in the
            queryset. Needed to verify if a user needs to be included in the recipient
            list of a deleted_* signal.
        Returns the enhanced queryset for the objects of this scope enhanced for better
        performances.
        """

        return self.get_base_queryset(include_trash=include_trash)

    def are_objects_child_of(
        self, child_objects: List[Any], parent_object: ScopeObject
    ) -> List[bool]:
        """
        Checks whether the given list of objects are all children of the given
        parent object.

        :param child_objects: The list of objects we want to check the scope belonging.
        :param parent_object: The parent object. The parent object must be an instance
            of the current model_class.
        :return: A boolean list that represents whether the object is child of the given
            parent for each object from parameter.
        """

        if not all([self.contains(child) for child in child_objects]):
            raise TypeError(
                f"The given child objects must be instance of {self.model_class}"
            )

        ids_in_scope = (
            self.get_base_queryset()
            .filter(self.get_filter_for_scopes(scopes=[parent_object]))
            .values_list("id", flat=True)
        )

        return [o.id in ids_in_scope for o in child_objects]

    def get_filter_for_scopes(self, scopes: List[Any]) -> Dict[Any, Any]:
        """
        Computes the filter to apply get all the objects instance of `self.model_class`
        included in the given scopes.

        :param scopes: A list of scopes we want the object for.
        :return: A Q object filter.
        """

        # Workspace scope by types to use `.get_filter_for_scope_type` later
        scope_by_types = defaultdict(set)
        for s in scopes:
            scope_by_types[object_scope_type_registry.get_by_model(s)].add(s)

        union_query = Q(id__in=[])

        for scope_type, scopes in scope_by_types.items():
            if scope_type.type == self.type:
                # Simple case: the scope type is the same as this one
                # Just filter by id
                union_query |= Q(id__in=[s.id for s in scopes])
            else:
                # Otherwise it's a parent scope. We add a part to the query_parts
                union_query |= self.get_filter_for_scope_type(scope_type, scopes)

        return union_query

    def get_objects_in_scopes(self, scopes: List[Any]) -> Dict[Any, Any]:
        """
        Computes the list of all objects, instance of the model_class property
        included in the given scopes.

        :param scopes: A list of scopes we want the object for.
        :return: A dict where the keys are the given scopes and the value is a list
          of the child objects of each scope.
        """

        objects_per_scope = {}
        parent_scope_types = set()

        parent_scopes = []
        for scope in scopes:
            object_scope_type = object_scope_type_registry.get_by_model(scope)
            if object_scope_type.type == self.type:
                # Scope of the same type doesn't need to be queried
                objects_per_scope[scope] = set([scope])
            else:
                parent_scopes.append(scope)
                objects_per_scope[scope] = set()
                parent_scope_types.add(object_scope_type)

        if parent_scopes:
            query_result = list(
                self.get_enhanced_queryset().filter(
                    self.get_filter_for_scopes(parent_scopes)
                )
            )

            # We have all the objects in the queryset, but now we want to sort them
            # into buckets per original scope they are a child of.
            for obj in query_result:
                for scope_type in parent_scope_types:
                    parent_scope = object_scope_type_registry.get_parent(
                        obj, at_scope_type=scope_type
                    )
                    if parent_scope in objects_per_scope:
                        objects_per_scope[parent_scope].add(obj)

        return objects_per_scope

    def contains(self, context: ContextObject):
        """
        Returns True if the context is one object of this context.

        :param context: The context to test
        :return: True if the ObjectScopeType of the context is the same as this one.
        """

        context_scope_type = object_scope_type_registry.get_by_model(context)
        return context_scope_type.type == self.type

    @cached_property
    def level(self) -> int:
        """
        Returns the level of this scope in the full object hierarchy. The level is the
        number of ancestor to get to the root object.

        :return: The level of the scope.
        """

        parent = self.get_parent_scope()
        if parent is None:
            return 0
        else:
            return parent.level + 1


class ObjectScopeTypeRegistry(
    Registry[ObjectScopeType], ModelRegistryMixin[Any, ObjectScopeType]
):
    """
    This registry contains all `ObjectScopeType`. It also proposes a set of methods
    useful to go through the full object/scope hierarchy.
    """

    name = "object_scope"

    def get_parent(self, context, at_scope_type=None):
        """
        Returns the parent object of the given context.

        :param context: The context object we want the parent for.
        :param at_scope_type: A parent scope at which you want the parent.
        :return: if the `at_scope_type` is not set: the parent object or `None` if it's
            a root object. If at_scope_type is set, the ancestor for which scope_type
            matches at_scope_type or None if no parents match.
        """

        context_scope_type = self.get_by_model(context)
        if at_scope_type:
            if at_scope_type.type == context_scope_type.type:
                return context
            else:
                parent_scope = context.get_parent()
                if parent_scope is None:
                    return None
                else:
                    return self.get_parent(parent_scope, at_scope_type=at_scope_type)
        else:
            return context.get_parent()

    def scope_includes_context(
        self,
        scope: ScopeObject,
        context: ContextObject,
        scope_type: Optional[ObjectScopeType] = None,
    ) -> bool:
        """
        Checks whether a scope object includes the given context.

        :param scope: The scope object.
        :param context: A context object.
        :scope_type: An optional `ObjectScopeType` that is used mainly for performance
            reason.
        :return: True if the context is included in the given scope object.
        """

        if context is None:
            return False

        scope_type = scope_type or self.get_by_model(scope)

        context_scope_type = self.get_by_model(context)

        if scope_type == context_scope_type:
            return scope.id == context.id
        else:
            return self.scope_includes_context(
                scope, context.get_parent(), scope_type=scope_type
            )

    def scope_type_includes_scope_type(
        self,
        parent_scope_type: ObjectScopeType,
        child_scope_type: ObjectScopeType,
    ) -> bool:
        """
        Checks whether the parent_scope includes the child_scope.

        :param parent_scope: The scope object or type that should includes the other
            scope.
        :param child_scope: The scope object or type that should be included by the
            other scope.
        :return: True if the parent_scope includes the children scope. False otherwise.
        """

        if child_scope_type is None:
            return False

        if parent_scope_type.type == child_scope_type.type:
            return True
        else:
            return self.scope_type_includes_scope_type(
                parent_scope_type,
                child_scope_type.get_parent_scope(),
            )

    does_not_exist_exception_class = ObjectScopeTypeDoesNotExist
    already_registered_exception_class = ObjectScopeTypeAlreadyRegistered


class SubjectType(abc.ABC, Instance, ModelInstanceMixin):
    """
    This type describes a subject that exists in Baserow. A subject is anything that
    can execute an operation.
    """

    def is_in_workspace(self, subject: Subject, workspace: "Workspace") -> bool:
        """
        This function checks if a subject belongs to a workspace
        :return: If the subject belongs to the workspace
        """

        return self.are_in_workspace([subject], workspace)[0]

    @abc.abstractmethod
    def are_in_workspace(
        self, subjects: List[Subject], workspace: "Workspace"
    ) -> List[bool]:
        """
        This function checks if the subjects belongs to a workspace
        :return: a list of bool. For each index whether the user at the same index
            belongs to the workspace or not
        """

        pass

    @abc.abstractmethod
    def get_serializer(self, model_instance, **kwargs) -> Serializer:
        """
        This function can be used to generate different serializers based on the type
        of subject that is being serialized
        :param model_instance: instance of a subject
        :param kwargs: additional kwargs that are parsed to serializer
        :return: the correct serializer for the subject
        """

        pass

    @abc.abstractmethod
    def get_users_included_in_subject(self, subject) -> List["AbstractUser"]:
        """
        Returns a list of Users which are associated with this subject.
        And associated user is any user that receives permissions in Baserow based
        on their link to this subject.
        :param subject: The subject we are trying to find the associated users for
        :return: All the associated users
        """

        pass


class SubjectTypeRegistry(Registry[SubjectType], ModelRegistryMixin[Any, SubjectType]):
    """
    This registry holds all the different subject types used across Baserow.
    """

    name = "subject"
    does_not_exist_exception_class = SubjectTypeNotExist

    def get_serializer(self, model_instance, **kwargs) -> Serializer:
        """
        This function is used to get the correct serializer for a given subject model
        instance. A SubjectType has to implement the `get_serializer` method in order
        to be serialized.
        :param model_instance: Instance of a subject
        :param kwargs: Additional kwargs passed to the serializer
        :return: The correct subject serializer
        """

        instance_type = self.get_by_model(model_instance)
        return instance_type.get_serializer(model_instance, **kwargs)


class OperationType(abc.ABC, Instance):
    """
    An `OperationType` represent an `Operation` an actor can do on a `ContextObject`.

    An OperationType must define a context_scope_name which is the name of the
    `ObjectScopeType` matching the context scope type related to the `ContextObject`

    Optionally an object_scope_name can be define to for list operations to express
    the scope of listed objects sometimes necessary for queryset filtering by the
    permission manager.
    """

    @classmethod
    @property
    @abc.abstractmethod
    def type(cls) -> str:
        """
        Should be a unique lowercase string used to identify this type.
        """

        pass

    @classmethod
    @property
    @abc.abstractmethod
    def context_scope_name(cls) -> str:
        """
        An operation is executed on a context in Baserow. For example the list_fields
        operation is executed on a table as it's context. Provide the context_scope_name
        here which matches a ObjectScopeType in the object_scope_type_registry.
        """

        pass

    object_scope_name: Optional[str] = None

    @cached_property
    def context_scope(self) -> ObjectScopeType:
        """
        Returns the `ObjectScopeType` related to the context_scope_name.
        """

        return object_scope_type_registry.get(self.context_scope_name)

    @cached_property
    def object_scope(self):
        """
        Returns the `ObjectScopeType` related to the object_scope_name. If the
        object_scope_name is not defined, then the object_scope is the same as the
        context_scope.
        """

        if self.object_scope_name:
            return object_scope_type_registry.get(self.object_scope_name)
        else:
            return self.context_scope


class OperationTypeRegistry(Registry[OperationType]):
    """
    Contains all the registered operation. For each registered operation, an Operation
    object is created in the database.
    """

    name = "operation"

    does_not_exist_exception_class = OperationTypeDoesNotExist
    already_registered_exception_class = OperationTypeAlreadyRegistered


class SerializationProcessorType(abc.ABC, Instance):
    """
    A registry instance that allows records to be annotated to the
    `import_serialized` and `export_serialized` methods.
    """

    @classmethod
    def import_serialized(
        cls,
        workspace: "Workspace",
        scope: SerializationProcessorScope,
        serialized_scope: dict,
        import_export_config: ImportExportConfig,
    ):
        """
        A hook which is called after an application subclass or table has been
        imported, allowing us to import additional data in `serialized_scope`.
        """

        pass

    @classmethod
    def export_serialized(
        cls,
        workspace: "Workspace",
        scope: SerializationProcessorScope,
        import_export_config: ImportExportConfig,
    ) -> Optional[Dict[str, Any]]:
        """
        A hook which is called after an application subclass or table has been
        exported, allowing us to export additional data.
        """

        return None


class SerializationProcessorRegistry(Registry[SerializationProcessorType]):
    """
    A registry which offers the ability to hook into application subclass
    and table post-`export_serialized` and post-`import_serialized` calls to
    perform serialization processing.
    """

    name = "serialization_processors"


class EmailContextType(abc.ABC, Instance):
    """
    An `EmailContextType` represents a context in which an email can be sent.
    """

    def get_context(self):
        raise NotImplementedError(
            "Must be implemented by the specific email context type"
        )


class EmailContextRegistry(Registry[EmailContextType]):
    name = "email_context"

    def get_context(self):
        """
        Return the context used to render the email template.
        Be aware that the order used to register the email context is important,
        because contexts are merged in the order they are registered.
        """

        context = {}
        for email_context in self.registry.values():
            context.update(**email_context.get_context())
        return context


# A default plugin and application registry is created here, this is the one that is
# used throughout the whole Baserow application. To add a new plugin or application use
# these registries.
plugin_registry = PluginRegistry()
application_type_registry = ApplicationTypeRegistry()
auth_provider_type_registry = AuthenticationProviderTypeRegistry()

permission_manager_type_registry: PermissionManagerTypeRegistry = (
    PermissionManagerTypeRegistry()
)
object_scope_type_registry: ObjectScopeTypeRegistry = ObjectScopeTypeRegistry()
subject_type_registry: SubjectTypeRegistry = SubjectTypeRegistry()
operation_type_registry: OperationTypeRegistry = OperationTypeRegistry()
serialization_processor_registry: SerializationProcessorRegistry = (
    SerializationProcessorRegistry()
)
email_context_registry: EmailContextRegistry = EmailContextRegistry()
