from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db import models as django_models

from rest_framework.fields import CharField
from rest_framework.serializers import Serializer

from baserow.contrib.database.fields.field_filters import OptionallyAnnotatedQ
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace, WorkspaceUser
from baserow.core.registries import (
    ImportExportConfig,
    OperationType,
    serialization_processor_registry,
)
from baserow.core.registry import (
    APIUrlsInstanceMixin,
    APIUrlsRegistryMixin,
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    ImportExportMixin,
    Instance,
    MapAPIExceptionsInstanceMixin,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)
from baserow.core.storage import ExportZipFile
from baserow.core.utils import (
    get_model_reference_field_name,
    split_attrs_and_m2m_fields,
)

from .exceptions import (
    AggregationTypeAlreadyRegistered,
    AggregationTypeDoesNotExist,
    DecoratorTypeAlreadyRegistered,
    DecoratorTypeDoesNotExist,
    DecoratorValueProviderTypeAlreadyRegistered,
    DecoratorValueProviderTypeDoesNotExist,
    ViewFilterTypeAlreadyRegistered,
    ViewFilterTypeDoesNotExist,
    ViewOwnershipTypeDoesNotExist,
    ViewTypeAlreadyRegistered,
    ViewTypeDoesNotExist,
)

if TYPE_CHECKING:
    from baserow.contrib.database.fields.models import Field
    from baserow.contrib.database.table.models import FieldObject, Table
    from baserow.contrib.database.views.models import FormView, View


class ViewType(
    MapAPIExceptionsInstanceMixin,
    APIUrlsInstanceMixin,
    CustomFieldsInstanceMixin,
    ModelInstanceMixin,
    ImportExportMixin,
    Instance,
):
    """
    This abstract class represents a custom view type that can be added to the
    view type registry. It must be extended so customisation can be done. Each view type
    will have his own model that must extend the View model, this is needed so that the
    user can set custom settings per view instance they have created.

    The added API urls will be available under the namespace 'api:database:views'.
    So if a url with name 'example' is returned by the method it will available under
    reverse('api:database:views:example').

    Example:
        from baserow.contrib.database.views.models import View
        from baserow.contrib.database.views.registry import ViewType, view_type_registry

        class ExampleViewModel(ViewType):
            pass

        class ExampleViewType(ViewType):
            type = 'unique-view-type'
            model_class = ExampleViewModel
            allowed_fields = ['example_ordering']
            serializer_field_names = ['example_ordering']
            serializer_field_overrides = {
                'example_ordering': serializers.CharField()
            }

            def get_api_urls(self):
                return [
                    path('view-type/', include(api_urls, namespace=self.type)),
                ]

        view_type_registry.register(ExampleViewType())
    """

    can_filter = True
    """
    Indicates if the view supports filters. If not, it will not be possible to add
    filter to the view.
    """

    can_sort = True
    """
    Indicates if the view support sortings. If not, it will not be possible to add a
    sort to the view.
    """

    can_aggregate_field = False
    """
    Indicates if the view supports field aggregation. If not, it will not be possible
    to compute fields aggregation for this view type.
    """

    can_decorate = False
    """
    Indicates if the view supports decoration. If not, it will not be possible
    to create decoration for this view type.
    """

    can_share = False
    """
    Indicates if the view supports being shared via a public link.
    """

    can_group_by = False
    """
    Indicates if the view supports grouping by fields. If not, it will not be possible
    to add a group by to the view.
    """

    can_list_rows = True
    """
    Indicates if the view supports listing rows. If not, it will not be possible to
    fetch rows from the view.
    """

    has_public_info = False
    """
    Indicates if the view supports public information being returned by
    the PublicViewInfoView.
    """

    field_options_model_class = None
    """
    The model class of the through table that contains the field options. The model
    must have a foreign key to the field and to the view.
    """

    field_options_serializer_class = None
    """
    The serializer class to serialize the field options model. It will be used in the
    API to update and list the field option, but it is also used to broadcast field
    option changes.
    """

    restrict_link_row_public_view_sharing = True
    """
    If a view is shared publicly, the `PublicViewLinkRowFieldLookupView` exposes all
    the primary values of every visible `link_row` field in the view. This property
    indicates whether the values should be restricted to existing relationships to
    the view.
    """

    when_shared_publicly_requires_realtime_events = True
    """
    If a view is shared publicly, this controls whether or not realtime row, field
    and view events will be available to subscribe to and sent to said subscribers.
    """

    field_options_allowed_fields = []
    """
    The field names that are allowed to set when creating and updating the field
    options
    """

    @property
    def model_reference_field_name(self):
        """
        Returns the name of the field that is used to reference the view model. This
        field is used to filter the field options based on the view.
        """

        from baserow.contrib.database.views.models import View

        field_options_model = self.field_options_model_class
        field_name = get_model_reference_field_name(field_options_model, View)
        return field_name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.can_share:
            self.allowed_fields = self.allowed_fields + ["public"]
            self.serializer_field_names = self.serializer_field_names + [
                "public",
                "slug",
            ]
            self.serializer_field_overrides = {
                **self.serializer_field_overrides,
                "slug": CharField(
                    read_only=True,
                    help_text="The unique slug that can be used to construct a public "
                    "URL.",
                ),
            }

    def export_serialized(
        self,
        view: "View",
        import_export_config: ImportExportConfig,
        cache: Optional[Dict] = None,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Dict[str, Any]:
        """
        Exports the view to a serialized dict that can be imported by the
        `import_serialized` method. This dict is also JSON serializable.

        :param view: The view instance that must be exported.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param cache: A cache to use for storing temporary data.
        :param files_zip: A zip file buffer where the files related to the export
            must be copied into.
        :param storage: The storage where the files can be loaded from.
        :return: The exported view.
        """

        serialized = {
            "id": view.id,
            "type": self.type,
            "name": view.name,
            "order": view.order,
            "ownership_type": view.ownership_type,
            "owned_by": view.owned_by.email if view.owned_by else None,
        }

        if self.can_filter:
            serialized["filter_type"] = view.filter_type
            serialized["filters_disabled"] = view.filters_disabled
            serialized["filters"] = [
                {
                    "id": view_filter.id,
                    "field_id": view_filter.field_id,
                    "type": view_filter.type,
                    "value": view_filter_type_registry.get(
                        view_filter.type
                    ).get_export_serialized_value(view_filter.value, cache),
                    "group": view_filter.group_id,
                }
                for view_filter in view.viewfilter_set.all()
            ]
            serialized["filter_groups"] = [
                {
                    "id": filter_group.id,
                    "filter_type": filter_group.filter_type,
                    "parent_group": filter_group.parent_group_id,
                }
                for filter_group in view.filter_groups.all()
            ]

        if self.can_sort:
            serialized["sortings"] = [
                {"id": sort.id, "field_id": sort.field_id, "order": sort.order}
                for sort in view.viewsort_set.all()
            ]

        if self.can_group_by:
            serialized["group_bys"] = [
                {
                    "id": group_by.id,
                    "field_id": group_by.field_id,
                    "order": group_by.order,
                }
                for group_by in view.viewgroupby_set.all()
            ]

        if self.can_decorate:
            serialized["decorations"] = [
                {
                    "id": deco.id,
                    "type": deco.type,
                    "value_provider_type": deco.value_provider_type,
                    "value_provider_conf": deco.value_provider_conf,
                    "order": deco.order,
                }
                for deco in view.viewdecoration_set.all()
            ]

        if self.can_share:
            serialized["public"] = view.public

        # It could be that there is no `table` related to the view when doing an
        # Airtable export, for example. That means it's not part of a workspace, so we
        # can't enhance the export with the `serialization_processor_registry`.
        if view.table_id is not None:
            for serialized_structure in serialization_processor_registry.get_all():
                extra_data = serialized_structure.export_serialized(
                    view.table.database.workspace, view, import_export_config
                )
                if extra_data is not None:
                    serialized.update(**extra_data)

        return serialized

    def import_serialized(
        self,
        table: "Table",
        serialized_values: Dict[str, Any],
        import_export_config: ImportExportConfig,
        id_mapping: Dict[str, Any],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
    ) -> Optional["View"]:
        """
        Imported an exported serialized view dict that was exported via the
        `export_serialized` method. Note that all the fields must be imported first
        because we depend on the new field id to be in the mapping.

        :param table: The table where the view should be added to.
        :param serialized_values: The exported serialized view values that need to
            be imported.
        :param import_export_config: provides configuration options for the
            import/export process to customize how it works.
        :param id_mapping: The map of exported ids to newly created ids that must be
            updated when a new instance has been created.
        :param files_zip: A zip file buffer where files related to the export can be
            extracted from.
        :param storage: The storage where the files can be copied to.
        :return: The newly created view instance or None if the view is not allowed to
            be imported according to its ownership type or the imported view has an
            unknown ownership type.
        """

        from .models import (
            DEFAULT_OWNERSHIP_TYPE,
            ViewDecoration,
            ViewFilter,
            ViewFilterGroup,
            ViewGroupBy,
            ViewSort,
        )

        if "database_views" not in id_mapping:
            id_mapping["database_views"] = {}
            # Must be kept in sync with
            # `src/baserow/contrib/database/table/handler.py::duplicate_table`
            id_mapping["database_view_filters"] = {}
            id_mapping["database_view_filter_groups"] = {}
            id_mapping["database_view_sortings"] = {}
            id_mapping["database_view_group_bys"] = {}
            id_mapping["database_view_decorations"] = {}

        if "owned_by" not in id_mapping:
            id_mapping["owned_by"] = {}

            owned_by_workspace = table.database.workspace

            if (
                id_mapping.get("import_workspace_id", None) is not None
                and owned_by_workspace is None
            ):
                owned_by_workspace = Workspace.objects.get(
                    id=id_mapping["import_workspace_id"]
                )

            if owned_by_workspace is not None:
                workspaceusers_from_workspace = WorkspaceUser.objects.filter(
                    workspace_id=owned_by_workspace.id
                ).select_related("user")

                for workspaceuser in workspaceusers_from_workspace:
                    id_mapping["owned_by"][
                        workspaceuser.user.email
                    ] = workspaceuser.user

        try:
            ownership_type = view_ownership_type_registry.get(
                serialized_values.get("ownership_type", DEFAULT_OWNERSHIP_TYPE)
            )
        except view_ownership_type_registry.does_not_exist_exception_class:
            return None

        # Backwards compatibility handling for case when serialized_values contains
        # "created_by" and not "owned_by" (field was renamed):
        if "owned_by" not in serialized_values:
            serialized_values["owned_by"] = serialized_values.pop("created_by", None)

        if not ownership_type.can_import_view(serialized_values, id_mapping):
            return None

        email = serialized_values.get("owned_by", None)

        serialized_values["owned_by"] = id_mapping["owned_by"].get(email, None)

        serialized_copy = serialized_values.copy()
        view_id = serialized_copy.pop("id")
        serialized_copy.pop("type")
        filters = serialized_copy.pop("filters") if self.can_filter else []
        filter_groups = (
            serialized_copy.pop("filter_groups", []) if self.can_filter else []
        )
        sortings = serialized_copy.pop("sortings") if self.can_sort else []
        group_bys = serialized_copy.pop("group_bys", []) if self.can_group_by else []
        decorations = (
            serialized_copy.pop("decorations", []) if self.can_decorate else []
        )

        view = self.model_class(table=table)
        # Only set the properties that are actually accepted by the view type's model
        # class.
        for key, value in serialized_copy.items():
            if hasattr(view, key):
                setattr(view, key, value)
        view.save()

        id_mapping["database_views"][view_id] = view.id

        if self.can_filter:
            for filter_group in filter_groups:
                filter_group_copy = filter_group.copy()
                filter_group_id = filter_group_copy.pop("id")
                filter_group_copy["view_id"] = view.id
                if filter_group_copy["parent_group"]:
                    filter_group_copy["parent_group_id"] = id_mapping[
                        "database_view_filter_groups"
                    ][filter_group_copy.pop("parent_group")]
                filter_group_object = ViewFilterGroup.objects.create(
                    view=view, **filter_group_copy
                )
                id_mapping["database_view_filter_groups"][
                    filter_group_id
                ] = filter_group_object.id

            for view_filter in filters:
                view_filter_type = view_filter_type_registry.get(view_filter["type"])
                view_filter_copy = view_filter.copy()
                view_filter_id = view_filter_copy.pop("id")
                view_filter_copy["field_id"] = id_mapping["database_fields"][
                    view_filter_copy["field_id"]
                ]
                view_filter_copy[
                    "value"
                ] = view_filter_type.set_import_serialized_value(
                    view_filter_copy["value"], id_mapping
                )
                if view_filter.get("group", None):
                    view_filter_copy["group_id"] = id_mapping[
                        "database_view_filter_groups"
                    ][view_filter_copy.pop("group")]
                view_filter_object = ViewFilter.objects.create(
                    view=view, **view_filter_copy
                )
                id_mapping["database_view_filters"][
                    view_filter_id
                ] = view_filter_object.id

        if self.can_sort:
            for view_sorting in sortings:
                view_sort_copy = view_sorting.copy()
                view_sort_id = view_sort_copy.pop("id")
                view_sort_copy["field_id"] = id_mapping["database_fields"][
                    view_sort_copy["field_id"]
                ]
                view_sort_object = ViewSort.objects.create(view=view, **view_sort_copy)
                id_mapping["database_view_sortings"][view_sort_id] = view_sort_object.id

        if self.can_group_by:
            for view_group_by in group_bys:
                view_group_by_copy = view_group_by.copy()
                view_group_by_id = view_group_by_copy.pop("id")
                view_group_by_copy["field_id"] = id_mapping["database_fields"][
                    view_group_by_copy["field_id"]
                ]
                view_group_by_object = ViewGroupBy.objects.create(
                    view=view, **view_group_by_copy
                )
                id_mapping["database_view_group_bys"][
                    view_group_by_id
                ] = view_group_by_object.id

        if self.can_decorate:
            for view_decoration in decorations:
                view_decoration_copy = view_decoration.copy()
                view_decoration_id = view_decoration_copy.pop("id")

                if view_decoration["value_provider_type"]:
                    try:
                        value_provider_type = (
                            decorator_value_provider_type_registry.get(
                                view_decoration["value_provider_type"]
                            )
                        )
                    except DecoratorValueProviderTypeDoesNotExist:
                        pass
                    else:
                        view_decoration_copy = (
                            value_provider_type.set_import_serialized_value(
                                view_decoration_copy, id_mapping
                            )
                        )

                view_decoration_object = ViewDecoration.objects.create(
                    view=view, **view_decoration_copy
                )
                id_mapping["database_view_decorations"][
                    view_decoration_id
                ] = view_decoration_object.id

        for (
            serialized_structure_processor
        ) in serialization_processor_registry.get_all():
            serialized_structure_processor.import_serialized(
                table.database.workspace, view, serialized_copy, import_export_config
            )

        return view

    def get_visible_fields_and_model(
        self, view: "View"
    ) -> Tuple[List["FieldObject"], django_models.Model]:
        """
        Returns the field objects for the provided view. Depending on the view type this
        will only return the visible or appropriate fields as different view types can
        hide or show fields based on their configuration.

        :param view: The view to get the fields for.
        :type view: View
        :return: An ordered list of field objects for this view and the model for the
            view.
        :rtype list, Model
        """

        model = view.table.get_model()
        return model._field_objects.values(), model

    def get_field_options_serializer_class(
        self, create_if_missing: bool = False
    ) -> Type[Serializer]:
        """
        Generates a serializer that has the `field_options` property as a
        `FieldOptionsField`. This serializer can be used by the API to validate or list
        the field options.

         :param create_if_missing: Whether or not to create any missing field options
            when looking them up during serialization.
        :raises ValueError: When the related view type does not have a field options
            serializer class.
        :return: The generated serializer.
        """

        from baserow.contrib.database.api.views.serializers import FieldOptionsField

        if not self.field_options_serializer_class:
            raise ValueError(
                f"The view type {self.type} does not have a field options serializer "
                f"class."
            )

        meta = type(
            "Meta",
            (),
            {"ref_name": self.type + "_view_field_options"},
        )

        attrs = {
            "Meta": meta,
            "field_options": FieldOptionsField(
                serializer_class=self.field_options_serializer_class,
                create_if_missing=create_if_missing,
            ),
        }

        return type(
            str("Generated" + self.type.capitalize() + "ViewFieldOptionsSerializer"),
            (Serializer,),
            attrs,
        )

    def before_field_options_update(
        self, view: "View", field_options: Dict[str, Any], fields: List["Field"]
    ) -> Dict[str, Any]:
        """
        Called before the field options are updated related to the provided view.

        :param view: The view for which the field options need to be updated.
        :param field_options: A dict with the field ids as the key and a dict
            containing the values that need to be updated as value.
        :param fields: Optionally a list of fields can be provided so that they don't
            have to be fetched again.
        :return: The updated field options.
        """

        return field_options

    def after_field_options_update(
        self,
        view: "View",
        field_options: Dict[str, Any],
        fields: List["Field"],
        update_field_option_instances: List[Any],
    ):
        """
        Called after the field options have been updated. This hook can be used to
        update values that haven't been updated.

        :param view: The view for which the field options need to be updated.
        :param field_options: A dict with the field ids as the key and a dict
            containing the values that need to be updated as value.
        :param fields: Optionally a list of fields can be provided so that they don't
            have to be fetched again.
        :param update_field_option_instances: The instances of the field options that
            have been updated.
        """

    def after_fields_type_change(self, fields: List["Field"]) -> None:
        """
        This hook is called after the type of a field has changed and gives the
        possibility to check compatibility with view stuff like specific field options.

        :param fields: The concerned fields.
        """

    def after_field_delete(self, field: "Field") -> None:
        """
        This hook is called after a field has been deleted and gives the possibility to
        clean up any related field options.

        :param field: The field that has been deleted.
        """

    def before_view_create(self, values: dict, table: "Table", user: AbstractUser):
        """
        Hook that's called before the view is created.

        :param values: The raw view values that were provided by the users.
        :param table: The table where the view is going to be created in.
        :param user: The user on whose behalf the view is created.
        """

    def before_view_update(self, values: dict, view: "View", user: AbstractUser):
        """
        Hook that's called before the view is updated.

        :param values: The raw view values that were provided by the users.
        :param view: The view that's going to be updated.
        :param user: The user on whose behalf the view is updated.
        """

    def prepare_values(
        self, values: Dict[str, Any], table: "Table", user: AbstractUser
    ) -> Dict[str, Any]:
        """
        The prepare_values hook gives the possibility to change the provided values
        just before they are going to be used to create or update the instance. For
        example if an ID is provided, it can be converted to a model instance. Or to
        convert a certain date string to a date object.

        :param values: The provided values.
        :param table: The table where the view is created in.
        :param user: The user on whose behalf the change is made.
        :return: The updates values.
        """

        return values

    def view_created(self, view: "View"):
        """
        A hook that's called when a new view is created.

        :param view: The newly created view instance.
        """

    def get_visible_field_options_in_order(
        self, view: "View"
    ) -> django_models.QuerySet:
        """
        Should return a queryset of all field options which are visible in the
        provided view and in the order they appear in the view.

        :param view: The view to query.
        :type view: View
        :return: A queryset of the views specific view options which are 'visible'
            and in order.
        """

        raise NotImplementedError(
            "An exportable or publicly sharable view must implement "
            "`get_visible_field_options_in_order`"
        )

    def get_aggregations(
        self, view: "View"
    ) -> Iterable[Tuple[django_models.Field, str]]:
        """
        Should return the aggregation list for the specified view.

        returns a list of tuple (Field, aggregation_type)
        """

        raise NotImplementedError(
            "If the view supports field aggregation it must implement "
            "`get_aggregations` method."
        )

    def after_field_value_update(
        self, updated_fields: Union[Iterable["Field"], "Field"]
    ):
        """
        Triggered for each field table value modification. This method is generally
        called after a row modification, creation, deletion and is called for each
        directly or indirectly modified field value. The method can be called multiple
        times for an event but with different fields. This hook gives a view type the
        opportunity to react on any value change for a field.

        :param updated_fields: a unique or a list of affected field.
        """

    def after_field_update(self, updated_fields: Union[Iterable["Field"], "Field"]):
        """
        Triggered after a field has been updated, created, deleted. This method is
        called for each workspace of field directly or indirectly modified this way.
        This hook gives a view type the opportunity to react on any change for a field.

        :param update_fields: a unique or a list of modified field.
        """

    def after_filter_update(self, view: "View"):
        """
        Triggered after a view filter change. This hook gives a view type the
        opportunity to react on any filter update.

        :param view: the view which filter has changed.
        """

    def export_prepared_values(self, view: "View") -> Dict[str, Any]:
        """
        Returns a serializable dict of prepared values for the view fields.
        This method is the counterpart of `prepare_values`. It is called
        by undo/redo ActionHandler to store the values in a way that could be
        restored later on in in the UpdateView handler calling the `prepare_values`
        method.

        :param view: The view to use for export.
        :return: A dict of prepared values for the provided fields.
        """

        values = {
            "name": view.name,
            "ownership_type": view.ownership_type,
            "filter_type": view.filter_type,
            "filters_disabled": view.filters_disabled,
            "public_view_password": view.public_view_password,
            "show_logo": view.show_logo,
        }

        allowed_attrs, m2m_fields = split_attrs_and_m2m_fields(
            self.allowed_fields, view
        )

        values.update({key: getattr(view, key) for key in allowed_attrs})
        values.update(
            {key: [item.id for item in getattr(view, key).all()] for key in m2m_fields}
        )

        return values

    def enhance_queryset(
        self, queryset: django_models.QuerySet
    ) -> django_models.QuerySet:
        """
        This hook can be used to enhance a queryset when fetching multiple views of a
        table. It will only be applied on the specific model queryset of the view.
        This is for example used by the signal when needs to fetch all the public
        views and figure out which fields are hidden. Meaning if you apply the
        `prefetch_related` and `select_related` here, they will be available in the
        `get_hidden_fields` method.

        :param queryset: The specific queryset that must be enhanced.
        :return: The enhanced queryset.
        """

        return queryset

    def enhance_field_options_queryset(
        self, queryset: django_models.QuerySet
    ) -> django_models.QuerySet:
        """
        This hook can be used to enhance the fetch field options queryset. If the
        field options have a relationship, `select_related` or `prefetch_related` can
        be applied here to improve performance.

        :param queryset: The queryset that must be enhanced.
        :return: The enhanced queryset.
        """

        return queryset

    def get_hidden_fields(
        self,
        view: "View",
        field_ids_to_check: Optional[List[int]] = None,
    ) -> Set[int]:
        """
        Should be implemented to return the set of fields ids which are not hidden
        in the provided view of this type. A hidden field as defined
        by this function will be completely excluded from any publicly
        shared version of this view.

        :param view: The view to find hidden field ids for.
        :param field_ids_to_check: An optional list of field ids to restrict the check
            down to.
        :return: A set of field ids which are hidden in this view.
        """

        raise NotImplementedError(
            "An exportable or publicly sharable view must implement "
            "`get_hidden_fields`"
        )

    def after_field_moved_between_tables(self, field: "Field", original_table_id: int):
        """
        This hook is called after a field has been moved between tables. It gives the
        view type the opportunity to react on the move to, for example, remove the
        field options have been created for the original table but are not needed
        anymore.

        :param field: The field that has been moved.
        :param original_table_id: The id of the table where the field was moved from.
        """

        self.field_options_model_class.objects.filter(
            **{
                f"{self.model_reference_field_name}__table_id": original_table_id,
                "field_id": field.id,
            }
        ).delete()

    def prepare_field_options(
        self, view: "View", field_id: "int"
    ) -> Type[django_models.Model]:
        """
        Returns the default field options for the provided view. This method can be
        overridden to provide custom default field options attributes. By default
        a field will be hidden if the view is public or if other fields are hidden.

        :param view: The view for which the default field options must be returned.
        :return: The default field options.
        """

        options_model_class = self.field_options_model_class
        view_field_options = getattr(
            view, f"{options_model_class._meta.model_name}_set"
        ).all()
        existing_options_field_ids = [option.field_id for option in view_field_options]

        model_class_default = options_model_class._meta.get_field("hidden").default
        hidden = (
            model_class_default
            or view.public
            or bool(self.get_hidden_fields(view, existing_options_field_ids))
        )

        return options_model_class(
            **{
                self.model_reference_field_name: view,
                "field_id": field_id,
                "hidden": hidden,
            },
        )

    def check_view_update_permissions(
        self, user: AbstractUser, view: "View", data: Dict[str, Any]
    ):
        """
        Hook that's called just before a view is updated. By default, it checks the
        `UpdateViewOperationType`, but when overwritten, it can optionally check for
        different permissions depending on the data. It returns nothing if the user has
        permissions, or raises a PermissionDenied error otherwise.

        :param user: The user on whose behalf the view is updated.
        :param view: The view instance that needs to be updated.
        :param data: The properties that need to be updated.
        :raises PermissionDenied: if the user doesn't have permissions to update the
            view.
        """

        from .operations import UpdateViewOperationType

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            user, UpdateViewOperationType.type, workspace=workspace, context=view
        )


class ViewTypeRegistry(
    APIUrlsRegistryMixin, CustomFieldsRegistryMixin, ModelRegistryMixin, Registry
):
    """
    With the view type registry it is possible to register new view types.  A view type
    is an abstraction made specifically for Baserow. If added to the registry a user can
    create new views based on this type.
    """

    name = "view"
    does_not_exist_exception_class = ViewTypeDoesNotExist
    already_registered_exception_class = ViewTypeAlreadyRegistered

    def get_field_options_serializer_map(self):
        return {
            view_type.type: view_type.get_field_options_serializer_class(
                create_if_missing=False
            )
            for view_type in self.registry.values()
        }


class ViewFilterType(Instance):
    """
    This abstract class represents a view filter type that can be added to the view
    filter type registry. It must be extended so customisation can be done. Each view
    filter type will have its own type names and rules. The get_filter method should
    be overwritten and should return a Q object that can be applied to the queryset
    later.

    Example:
        from baserow.contrib.database.views.registry import (
            ViewFilterType, view_filter_type_registry
        )

        class ExampleViewFilterType(ViewFilterType):
            type = 'equal'
            compatible_field_types = ['text', 'long_text']

            def get_filter(self, field_name, value):
                return Q(**{
                    field_name: value
                })

        view_filter_type_registry.register(ExampleViewFilterType())
    """

    compatible_field_types: List[Union[str, Callable[["Field"], bool]]] = []
    """
    Defines which field types are compatible with the filter. The values in this list
    can either be the literal `FieldType.type` string, or a callable taking the
    concrete field and returning True/False. When checking compatibility the
    `FieldType.get_compatible_filter_field_type(field)` indirection is applied first,
    allowing field types to alias themselves to another type for filtering purposes.
    """

    def default_filter_on_exception(self):
        """The default Q to use when the filter value is of an incompatible type."""

        return django_models.Q(pk__in=[])

    def get_filter(self, field_name, value, model_field, field) -> OptionallyAnnotatedQ:
        """
        Should return either a Q object or and AnnotatedQ containing the requested
        filtering and annotations based on the provided arguments.

        :param field_name: The name of the field that needs to be filtered.
        :type field_name: str
        :param value: The value that the field must be compared to.
        :type value: str
        :param model_field: The field extracted from the model.
        :type model_field: models.Field
        :param field: The instance of the underlying baserow field.
        :type field: Field
        :return: A Q or AnnotatedQ filter for this specific field, which will be then
            later combined with other filters to generate the final total view filter.
        """

        raise NotImplementedError("Each must have his own get_filter method.")

    def get_preload_values(self, view_filter) -> dict:
        """
        Optionally a view filter type can preload certain values for displaying
        purposes. This is for example used by the `link_row_has` filter type to
        preload the name of the chosen row.

        :param view_filter: The view filter instance object where the values must be
            preloaded for.
        :type view_filter: ViewFilter
        :return: The preloaded values as a dict.
        """

        return {}

    def get_export_serialized_value(self, value: str | None, id_mapping: dict) -> str:
        """
        This method is called before the filter value is exported. Here it can
        optionally be modified.

        :param value: The original value.
        :param id_mapping: Cache for mapping object ids.
        :return: The updated value.
        """

        if value is None:
            return ""
        return value

    def set_import_serialized_value(self, value: str | None, id_mapping: dict) -> str:
        """
        This method is called before a field is imported. It can optionally be
        modified. If the value for example points to a field or select option id, it
        can be replaced with the correct value by doing a lookup in the id_mapping.

        :param value: The original exported value.
        :param id_mapping: The map of exported ids to newly created ids that must be
            updated when a new instance has been created.
        :return: The new value that will be imported.
        """

        if value is None:
            return ""
        return value

    def field_is_compatible(self, field: "Field") -> bool:
        """
        Given a particular instance of a field returns a list of Type[FieldType] which
        are compatible with this particular field type.

        Works by checking the field's canonical filter type (as returned by
        `FieldType.get_compatible_filter_field_type(field)`) against this filter's
        `compatible_field_types`.

        :param field: The field to check.
        :return: True if the field is compatible, False otherwise.
        """

        from baserow.contrib.database.fields.registries import field_type_registry

        field_type = field_type_registry.get_by_model(field.specific_class)
        # Allow field types to map themselves to another field type for filter
        # compatibility checks.
        compatible_field_type = field_type.get_compatible_filter_field_type(field)

        return any(
            (callable(t) and t(field)) or t == compatible_field_type.type
            for t in self.compatible_field_types
        )

    @property
    def time_sensitive(self) -> bool:
        """
        Indicates if the filter results depend on the current time.
        For example, filters like 'date_is' with operators like `today` or `yesterday`
        will return different results as time passes, even if the underlying
        data hasn't changed.

        :returns: True if the filter results change based on current time
        """

        return False


class ViewFilterTypeRegistry(Registry):
    """
    With the view filter type registry is is possible to register new view filter
    types. A view filter type is an abstractions that allows different types of
    filtering for rows in a view. It is possible to add multiple view filters to a view
    and all the rows must match those filters.
    """

    name = "view_filter"
    does_not_exist_exception_class = ViewFilterTypeDoesNotExist
    already_registered_exception_class = ViewFilterTypeAlreadyRegistered

    def get_time_sensitive_filter_types(self) -> List[str]:
        """
        Returns a list of filter types that are time-dependent. For example, filters
        like `date_is` with operators like `today` or `yesterday` will return different
        results as time passes, even if the underlying data hasn't changed.

        :returns: A list of filter types that are time-sensitive
        """

        return [
            filter_type.type
            for filter_type in self.registry.values()
            if filter_type.time_sensitive
        ]


class ViewAggregationType(Instance):
    """
    If you want to aggregate the values of fields in a view, you can use a field
    aggregation. For example you can compute a sum of all values of a field in a table.
    """

    allowed_in_view = True

    def get_aggregation(
        self,
        field_name: str,
        model_field: django_models.Field,
        field: "Field",
    ) -> django_models.Aggregate:
        """
        Should return the requested django aggregation object based on
        the provided arguments.

        :param field_name: The name of the field that needs to be aggregated.
        :type field_name: str
        :param model_field: The field extracted from the model.
        :type model_field: django_models.Field
        :param field: The instance of the underlying baserow field.
        :type field: Field
        :return: A django aggregation object for this specific field.
        """

        raise NotImplementedError(
            "Each aggregation type must have his own get_aggregation method."
        )

    def field_is_compatible(self, field: "Field") -> bool:
        """
        Given a particular instance of a field returns whether the field is supported
        by this aggregation type or not.

        :param field: The field to check.
        :return: True if the field is compatible, False otherwise.
        """

        from baserow.contrib.database.fields.registries import field_type_registry

        field_type = field_type_registry.get_by_model(field.specific_class)

        return any(
            callable(t) and t(field) or t == field_type.type
            for t in self.compatible_field_types
        )


class ViewAggregationTypeRegistry(Registry):
    """
    This registry contains all the available field aggregation operators. A field
    aggregation allow to summarize all the values for a specific field of a table.
    """

    name = "field_aggregation"
    does_not_exist_exception_class = AggregationTypeDoesNotExist
    already_registered_exception_class = AggregationTypeAlreadyRegistered


class DecoratorType(Instance):
    """
    By declaring a new `DecoratorType` you allow a new decorator type to be created.
    """

    def before_create_decoration(self, view, user: Union[AbstractUser, None]):
        """
        This hook is called before a new decoration is created with this type.

        :param view: The view where the decoration is created in.
        :param user: Optionally a user on whose behalf the decoration is created.
        """

    def before_update_decoration(
        self, view_decoration, user: Union[AbstractUser, None]
    ):
        """
        This hook is called before an existing decoration is updated to this type.

        :param view_decoration: The view decoration that's being updated.
        :param user: Optionally a user on whose behalf the decoration is updated.
        """


class DecoratorTypeRegistry(Registry):
    """This registry contains decorators types."""

    name = "decorator"
    does_not_exist_exception_class = DecoratorTypeDoesNotExist
    already_registered_exception_class = DecoratorTypeAlreadyRegistered


class DecoratorValueProviderType(CustomFieldsInstanceMixin, Instance):
    """
    By declaring a new `DecoratorValueProviderType` you can define hooks on events that
    can affect the decoration value provider configuration.
    """

    value_provider_conf_serializer_class = None
    compatible_decorator_types: List[Union[str, Callable[[DecoratorType], bool]]] = []
    """
    A list of compatible decorator type names. This list can also contain functions,
    these functions must take one argument which is the decorator type and return
    whether this type is compatible or not with the value provider.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.value_provider_conf_serializer_class:
            raise ValueError(
                f"The decorator value provider type {self.type} does not have a "
                "value_provider_conf_serializer_class."
            )

        self.serializer_field_overrides = {
            "value_provider_conf": self.value_provider_conf_serializer_class(
                required=False,
                help_text="The configuration of the value provider",
            ),
        }

    def before_create_decoration(self, view, user: Union[AbstractUser, None]):
        """
        This hook is called before a new decoration is created with this type.

        :param view: The view where the decoration is created in.
        :param user: Optionally a user on whose behalf the decoration is created.
        """

    def before_update_decoration(
        self, view_decoration, user: Union[AbstractUser, None]
    ):
        """
        This hook is called before an existing decoration is updated to this type.

        :param view_decoration: The view decoration that's being updated.
        :param user: Optionally a user on whose behalf the decoration is updated.
        """

    def set_import_serialized_value(
        self, value: Dict[str, Any], id_mapping: Dict[str, Dict[int, Any]]
    ) -> Dict[str, Any]:
        """
        This method is called before a decorator is imported. It can optionally be
        modified. If the value_provider_conf for example points to a field or select
        option id, it can be replaced with the correct value by doing a lookup in the
        id_mapping.

        :param value: The original exported value.
        :param id_mapping: The map of exported ids to newly created ids that must be
            updated when a new instance has been created.
        :return: The new value that will be imported.
        """

        return value

    def after_field_delete(self, deleted_field: "Field"):
        """
        Triggered after a field has been deleted.
        This hook gives the opportunity to react when a field is deleted.

        :param deleted_field: the deleted field.
        """

    def after_fields_type_change(self, fields: List["Field"]):
        """
        This hook is called after the type of a field has changed and gives the
        possibility to check compatibility or update configuration.

        :param fields: The concerned fields.
        """

    def get_serializer_class(self, *args, **kwargs):
        # Add meta ref name to avoid name collision
        return super().get_serializer_class(
            *args,
            meta_ref_name=f"Generated{self.type.capitalize()}{kwargs['base_class'].__name__}",
            **kwargs,
        )

    def decorator_is_compatible(self, decorator_type: DecoratorType) -> bool:
        """
        Given a particular decorator type returns whether it is compatible
        with this value_provider type or not.

        :param decorator_type: The decorator type to check.
        :return: True if the value_provider_type is compatible, False otherwise.
        """

        return any(
            callable(t) and t(decorator_type) or t == decorator_type.type
            for t in self.compatible_decorator_types
        )

    @property
    def model_class(self):
        from baserow.contrib.database.views.models import ViewDecoration

        return ViewDecoration


class DecoratorValueProviderTypeRegistry(Registry):
    """
    This registry contains declared decorator value provider if needed.
    """

    name = "decorator_value_provider_type"
    does_not_exist_exception_class = DecoratorValueProviderTypeDoesNotExist
    already_registered_exception_class = DecoratorValueProviderTypeAlreadyRegistered


class FormViewModeType(Instance):
    def before_form_create(self, values: dict, table: "Table", user: AbstractUser):
        """
        Hook that's called before the form view is created.

        :param values: The raw form view values that were provided by the users.
        :param table: The table where the form view is going to be created in.
        :param user: The user on whose behalf the form view is created.
        """

    def before_form_update(self, values: dict, form: "FormView", user: AbstractUser):
        """
        Hook that's called before the form view is updated.

        :param values: The raw form view values that were provided by the users.
        :param view: The view that's going to be updated.
        :param user: The user on whose behalf the form view is updated.
        """


class FormViewModeRegistry(Registry):
    """
    This registry holds all the user configurable form mode types. It doesn't offer
    any functionality at the moment, apart from validation.
    """

    name = "form_view_mode"

    def get_default_type(self):
        return list(self.get_all())[0]

    def get_default_choice(self) -> str:
        return str(self.get_types()[0])

    def get_choices(self) -> List[Tuple[str, str]]:
        return [(t, t) for t in form_view_mode_registry.get_types()]


class ViewOwnershipType(Instance):
    """
    A `ViewOwnershipType` represents allowed style of view ownership.
    """

    def can_import_view(self, serialized_data: Dict, id_mapping: Dict) -> bool:
        """
        Returns True if the a view with this ownership can be imported.
        """

        return True

    def get_trashed_item_owner(self, view):
        """Returns the owner of the trashed item."""

        return None

    def should_broadcast_signal_to(
        self, view: "View"
    ) -> Tuple[Literal["table", "users", "refresh", ""], Optional[List[int]]]:
        """
        Returns a tuple that represent the kind of signaling that must be done for the
        given view.

        :param view: the view we want to send the signal for.
        :return: The first element of the tuple must be "" if no signaling is needed,
            "users" if signal has to be send to a list of users and "table" if the
            signal can be send to all the users of the view table. "refresh" if the
            view and table data must be refreshed.
            The second member of the tuple can be any object necessary for the signal
            depending of the type.
            If the signal type is "users", it must be a list of user ids.
            For other type it's None.
        """

        return "table", None

    def before_form_view_submitted(self, form, request):
        """
        Called before a form view of this ownership type is submitted. Can be used
        to perform extra permission checks and raise an exception if something is
        wrong.

        :param form: The form being submitted
        :param request: The submission request
        :return: Nothing
        """

        pass

    def before_public_view_accessed(self, view):
        """
        Called before a view of this ownership type which is publicly shared is
        accessed. Can be used to perform extra permission checks and raise an exception
        if something is wrong.

        :param view: The publicly shared view being accessed.
        :return: Nothing
        """

        pass

    def get_operation_to_check_to_create_view(self) -> Type[OperationType]:
        """
        :return: An OperationType that the user must have to create a view of this
            ownership type
        """

        from .operations import CreateViewOperationType

        return CreateViewOperationType

    def change_ownership_type(self, user: AbstractUser, view: "View") -> "View":
        """
        Changes the view `ownership_type` attribute and sets provided User as
        the owner of the view (`View.owned_by`).

        This method is usually overridden in classes that subclass this base
        class (f. ex. `CollaborativeViewOwnershipType`,
        `PersonalViewOwnershipType`), where additional required permissions to
        change the ownership type for the view are checked (if needed).

        For the above reason and to prioritize security, keep the system fuctional
        in case of new `ownership_types` are added, this base class raises
        `PermissionDenied` error by default.

        :param user: The user who want to change the ownership type
        :param view: The view whose ownership type is being changed
        :return: The updated view
        """

        raise PermissionDenied()

    def view_created(self, user: AbstractUser, view: "View", workspace: Workspace):
        """
        Hook that is called after a view is created. This can be used to introduce
        additional permissions checks, for example.

        :param user: The user that created the view.
        :param view: The view that was created.
        :param workspace: The workspace where the view was created in.
        """

    def enforce_apply_filters(self, user: Optional[AbstractUser], view: "View") -> bool:
        """
        A hook that if it returns `True`, enforces the filters of the view to be
        applied, regardless any other settings like adhoc filters. This can be used to
        ensure that unfiltered rows are never exposed.

        :param user: The user on whose behalf the rows are requested.
        :param view: The related view.
        :return: Boolean indicating whether the apply filters should be enforced.
        """

        return False

    def prepare_views_for_user(
        self, user: Optional[AbstractUser], views: List["View"]
    ) -> List["View"]:
        """
        A hook that can be used to make changes to the provided view objects `views` if
        needed for the view ownership type. Only views of the related type are provided
        here. This can be used to add or remove properties from the object if needed.

        :param user: The user on whose behalf the view objects are enhanced. Can be
            used for permission checking. Note that it's not always provided.
        :param views: The views to enhance.
        :return: The enhanced views.
        """

        return views

    def can_modify_rows(
        self, view: "View", row_ids: Optional[List[int]] = None
    ) -> bool:
        """
        Indicates whether it's possible to modify rows in the view, even if the user
        does not have permissions to the table. The role that the user has on view
        level must of course include the `CreateViewRowOperationType`,
        `UpdateViewRowOperationType`, and `DeleteViewRowOperationType` operations.

        :param view: The view where to check the permissions for.
        :param row_ids: Optionally a list of row ids that are modified. This way, an
            extra check can be performed.
        :return: Returns true if it's possible to modify rows in the view.
        """

        return False


class ViewOwnershipTypeRegistry(Registry):
    """
    Contains all registered view ownership types.
    """

    name = "view_ownership_type"
    does_not_exist_exception_class = ViewOwnershipTypeDoesNotExist

    def prepare_views_of_different_types_for_user(
        self, user: AbstractUser, views: List["View"]
    ) -> List["View"]:
        """
        Loops over the provided views and per ownership type, calls the
        `enhance_view_objects` method.

        :param user: The user on whose behalf the views are requested. Can be used for
            permission checks.
        :param views: The views that must be enhanced.
        :return: The enhanced views.
        """

        for view_ownership_type in self.get_all():
            views_of_type = [
                view
                for view in views
                if view.ownership_type == view_ownership_type.type
            ]
            views_of_type = view_ownership_type.prepare_views_for_user(
                user, views_of_type
            )
            # Put the enhanced view back into the original list at the right index so
            # that the order is not changed.
            for view_of_type in views_of_type:
                for index, view in enumerate(views):
                    if view.id == view_of_type.id:
                        views[index] = view_of_type
                        break

        return views


# A default view type registry is created here, this is the one that is used
# throughout the whole Baserow application to add a new view type.
view_type_registry = ViewTypeRegistry()
view_filter_type_registry = ViewFilterTypeRegistry()
view_aggregation_type_registry = ViewAggregationTypeRegistry()
decorator_type_registry = DecoratorTypeRegistry()
decorator_value_provider_type_registry = DecoratorValueProviderTypeRegistry()
form_view_mode_registry = FormViewModeRegistry()
view_ownership_type_registry: ViewOwnershipTypeRegistry = ViewOwnershipTypeRegistry()
