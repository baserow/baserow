import dataclasses
import itertools
import re
import traceback
from collections import defaultdict, namedtuple
from copy import deepcopy
from hashlib import shake_128
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Type, Union

from django.conf import settings
from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db import connection
from django.db import models as django_models
from django.db.models import Count, Q
from django.db.models.expressions import OrderBy
from django.db.models.query import QuerySet

import jwt
from loguru import logger
from opentelemetry import trace
from redis.exceptions import LockNotOwnedError

from baserow.contrib.database.api.utils import get_include_exclude_field_ids
from baserow.contrib.database.db.schema import safe_django_schema_editor
from baserow.contrib.database.fields.exceptions import FieldNotInTable
from baserow.contrib.database.fields.field_filters import (
    AdvancedFilterBuilder,
    FilterBuilder,
)
from baserow.contrib.database.fields.field_sortings import OptionallyAnnotatedOrderBy
from baserow.contrib.database.fields.models import Field, LinkRowField
from baserow.contrib.database.fields.operations import ReadFieldOperationType
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.search.handler import SearchMode
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.exceptions import ViewOwnershipTypeDoesNotExist
from baserow.contrib.database.views.filters import AdHocFilters
from baserow.contrib.database.views.operations import (
    CreatePublicViewOperationType,
    CreateViewDecorationOperationType,
    CreateViewFilterGroupOperationType,
    CreateViewFilterOperationType,
    CreateViewGroupByOperationType,
    CreateViewSortOperationType,
    DeleteViewDecorationOperationType,
    DeleteViewFilterGroupOperationType,
    DeleteViewFilterOperationType,
    DeleteViewGroupByOperationType,
    DeleteViewOperationType,
    DeleteViewSortOperationType,
    DuplicateViewOperationType,
    ListAggregationsViewOperationType,
    ListViewDecorationOperationType,
    ListViewFilterOperationType,
    ListViewGroupByOperationType,
    ListViewsOperationType,
    ListViewSortOperationType,
    OrderViewsOperationType,
    ReadAggregationsViewOperationType,
    ReadViewDecorationOperationType,
    ReadViewFieldOptionsOperationType,
    ReadViewFilterGroupOperationType,
    ReadViewFilterOperationType,
    ReadViewGroupByOperationType,
    ReadViewOperationType,
    ReadViewsOrderOperationType,
    ReadViewSortOperationType,
    UpdateViewDecorationOperationType,
    UpdateViewFieldOptionsOperationType,
    UpdateViewFilterGroupOperationType,
    UpdateViewFilterOperationType,
    UpdateViewGroupByOperationType,
    UpdateViewPublicOperationType,
    UpdateViewSlugOperationType,
    UpdateViewSortOperationType,
)
from baserow.contrib.database.views.registries import (
    ViewType,
    view_ownership_type_registry,
)
from baserow.contrib.database.views.view_filter_groups import ViewGroupedFiltersAdapter
from baserow.core.db import specific_iterator, sql, transaction_atomic
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.registries import ImportExportConfig
from baserow.core.telemetry.utils import baserow_trace_methods
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import (
    MirrorDict,
    atomic_if_not_already,
    extract_allowed,
    find_unused_name,
    get_model_reference_field_name,
    set_allowed_attrs,
    set_allowed_m2m_fields,
    split_attrs_and_m2m_fields,
)

from .exceptions import (
    CannotShareViewTypeError,
    DecoratorValueProviderTypeNotCompatible,
    FieldAggregationNotSupported,
    NoAuthorizationToPubliclySharedView,
    UnrelatedFieldError,
    ViewDecorationDoesNotExist,
    ViewDecorationNotSupported,
    ViewDoesNotExist,
    ViewDoesNotSupportFieldOptions,
    ViewDoesNotSupportListingRows,
    ViewFilterDoesNotExist,
    ViewFilterGroupDoesNotExist,
    ViewFilterNotSupported,
    ViewFilterTypeNotAllowedForField,
    ViewGroupByDoesNotExist,
    ViewGroupByFieldAlreadyExist,
    ViewGroupByFieldNotSupported,
    ViewGroupByNotSupported,
    ViewNotInTable,
    ViewSortDoesNotExist,
    ViewSortFieldAlreadyExist,
    ViewSortFieldNotSupported,
    ViewSortNotSupported,
)
from .models import (
    DEFAULT_SORT_TYPE_KEY,
    OWNERSHIP_TYPE_COLLABORATIVE,
    View,
    ViewDecoration,
    ViewFilter,
    ViewFilterGroup,
    ViewGroupBy,
    ViewRows,
    ViewSort,
    ViewSubscription,
)
from .registries import (
    decorator_type_registry,
    decorator_value_provider_type_registry,
    view_aggregation_type_registry,
    view_filter_type_registry,
    view_type_registry,
)
from .signals import (
    form_submitted,
    rows_entered_view,
    rows_exited_view,
    view_created,
    view_decoration_created,
    view_decoration_deleted,
    view_decoration_updated,
    view_deleted,
    view_field_options_updated,
    view_filter_created,
    view_filter_deleted,
    view_filter_group_created,
    view_filter_group_deleted,
    view_filter_group_updated,
    view_filter_updated,
    view_group_by_created,
    view_group_by_deleted,
    view_group_by_updated,
    view_sort_created,
    view_sort_deleted,
    view_sort_updated,
    view_updated,
    views_reordered,
)
from .utils import AnnotatedAggregation, DistributionAggregation
from .validators import value_is_empty_for_required_form_field

FieldOptionsDict = Dict[int, Dict[str, Any]]


ending_number_regex = re.compile(r"(.+) (\d+)$")

tracer = trace.get_tracer(__name__)


PerViewTableIndexUpdate = namedtuple(
    "PerViewTableIndexUpdate", "all_indexes added removed"
)


@dataclasses.dataclass
class UpdatedViewWithChangedAttributes:
    updated_view_instance: View
    original_view_attributes: Dict[str, Any]
    new_view_attributes: Dict[str, Any]


class ViewIndexingHandler(metaclass=baserow_trace_methods(tracer)):
    @classmethod
    def does_index_exist(cls, index_name: str) -> bool:
        """
        Returns whether or not the given index exists in the database.

        :param index_name: The name of the index to check for.
        :return: Whether or not the given index exists in the database.
        """

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes WHERE indexname = %s",
                [index_name],
            )
            return cursor.fetchone() is not None

    @classmethod
    def _get_index_name_prefix(cls, table_id: int) -> str:
        """
        Returns the prefix for the index. Different views can share the same
        index when the same sortings are used to save disk space, so the
        table_id will be used instead of the more obvious view_id.

        :param table_id: The id of the table.
        :return: The index prefix.
        """

        return f"i{table_id}:"

    @classmethod
    def before_field_type_change(cls, field: Field, model=None):
        """
        Remove all the indexes for the views that have a sort on the field
        that is being changed.

        :param field: The field that is being changed.
        :param model: The model to use for the table. If not provided it will be
            taken from the field.
        """

        views = View.objects.filter(
            id__in=ViewSort.objects.filter(field=field).values("view_id"),
            db_index_name__isnull=False,
        )
        if not views:
            return

        if model is None:
            model = field.table.get_model()

        dropped_indexes = set()
        for view in views:
            if view.db_index_name in dropped_indexes:
                continue

            cls.drop_index(
                view=view,
                db_index=django_models.Index("id", name=view.db_index_name),
                model=model,
            )
            dropped_indexes.add(view.db_index_name)

        View.objects.filter(id__in=[v.id for v in views]).update(db_index_name=None)

    @classmethod
    def _get_index_hash(
        cls, field_order_bys: List[OptionallyAnnotatedOrderBy]
    ) -> Optional[str]:
        """
        Returns a key used for sorting a view.
        View sharing the same key will have the same index name, so that the
        index can be reused.

        :param field_order_bys: List of order bys that form the sort on a view.
        :return: The index hash key calculated from the fields used for sorting.
        """

        def concat_attrs(field_order_by):
            collation = (
                f":{field_order_by.collation}" if field_order_by.collation else ""
            )
            return f"{field_order_by.field_expression}{collation}:{field_order_by.order.descending}"

        index_key = "-".join(
            map(
                concat_attrs,
                field_order_bys,
            )
        )
        # limit to 20 characters, considering the limit of 30 for the index name
        return shake_128(index_key.encode("utf-8")).hexdigest(10)

    @classmethod
    def get_index_name(
        cls, table_id: int, field_order_bys: List[OptionallyAnnotatedOrderBy]
    ) -> str:
        """
        Returns the name of the index for a view based on provided field sortings.

        :param table_id: The id of the table.
        :param field_order_bys: List of order bys that form the sort on a view.
        :return: The index name.
        """

        index_name_prefix = cls._get_index_name_prefix(table_id)
        index_hash = cls._get_index_hash(field_order_bys)
        return f"{index_name_prefix}{index_hash}"

    @classmethod
    def schedule_index_creation_if_needed(cls, view: View, model: GeneratedTableModel):
        """
        Schedules the creation of the index in an asynchronous task if the index
        is missing and the view uses some sort of ordering for which it makes sense
        to create an index for.

        :param view: The view to schedule the index creation for.
        :param model: The table model for which the view index should be
            generated.
        """

        view_type = view_type_registry.get_by_model(view)
        if not view_type.can_sort and not view_type.can_group_by:
            return

        try:
            db_index = cls.get_index(view, model)
            if db_index is not None and db_index.name != view.db_index_name:
                cls.schedule_index_update(view)
        except Exception as exc:  # nosec
            logger.error(
                "Failed to check if view needs index because of {e}", e=str(exc)
            )
            traceback.print_exc()

    @classmethod
    def get_index(
        cls, view: View, model: Optional[GeneratedTableModel] = None
    ) -> Optional[django_models.Index]:
        """
        Returns the model and the best possible index for the requested view.

        :param view: The view to get the model and index for.
        :param model: The table model for which the view index should be
            generated.
        :return: The index for view or None for the default order or if an
            index cannot be created because of annotations or ordering based on
            other tables fields.
        """

        if model is None:
            model = view.table.get_model()

        field_order_bys = []

        for view_sort_or_group_by in view.get_all_sorts():
            field_object = model._field_objects[view_sort_or_group_by.field_id]
            annotated_order_by = field_object["type"].get_order(
                field_object["field"],
                field_object["name"],
                view_sort_or_group_by.order,
                view_sort_or_group_by.type,
                table_model=model,
            )

            # It's enough to have one field that cannot be indexed to make the DB
            # very likely to not use the index, so just return None here.
            if not annotated_order_by.can_be_indexed:
                return None

            field_order_bys.append(annotated_order_by)

        index_fields = [o for ob in field_order_bys for o in ob.order_bys]

        if not index_fields:
            return None

        index_name = cls.get_index_name(view.table_id, field_order_bys)
        return django_models.Index(
            *index_fields,
            "order",
            "id",
            condition=Q(trashed=False),
            name=index_name,
        )

    @classmethod
    def before_view_permanently_deleted(cls, view: View):
        """
        Called when a view is permanently deleted. This will remove the view
        index if no longer required.

        :param view: The view that was deleted.
        """

        return cls.drop_index_if_unused(view)

    @classmethod
    def after_fields_changed_or_deleted(cls, fields: List[Field]):
        """
        Called when a field is deleted. This will remove any indexes that are no
        longer required.

        :param field: The field that was deleted.
        """

        views_need_to_be_updated = View.objects.filter(
            Q(viewsort__field_id__in=[field.id for field in fields])
            | Q(viewgroupby__field_id__in=[field.id for field in fields]),
            db_index_name__isnull=False,
        )
        for view in views_need_to_be_updated:
            cls.schedule_index_update(view)

    @classmethod
    def schedule_index_update(cls, view: View):
        """
        This function schedules a celery task calling the update_view_index
        method to update the index for the specific view.

        :param view: The view for which the index needs to be updated.
        """

        from baserow.contrib.database.views.tasks import schedule_view_index_update

        schedule_view_index_update(view.pk)

    @classmethod
    def create_index_if_not_exists(
        cls,
        view: View,
        model: GeneratedTableModel,
        db_index: django_models.Index,
    ) -> Optional[str]:
        """
        Creates a new index for the provided view if it does not exist yet.

        :param view: The view to create the index for.
        :param model: The model to use for the table. If not provided it will be
            generated.
        :param db_index: The index to create.
        :return: The name of the index for the current view if any.
        """

        other_view_using_index = View.objects.filter(
            db_index_name=db_index.name, table=view.table
        ).exclude(pk=view.pk)

        if other_view_using_index.exists() or cls.does_index_exist(db_index.name):
            return db_index.name

        with safe_django_schema_editor() as schema_editor:
            schema_editor.add_index(model, db_index)
            logger.info(
                "Created Index {db_index_name} for view {view_pk} of table {view_table_id}",
                db_index_name=db_index.name,
                view_pk=view.pk,
                view_table_id=view.table_id,
            )

        return db_index.name

    @classmethod
    def drop_index_if_unused(
        cls, view: View, model: Optional[GeneratedTableModel] = None
    ) -> Optional[str]:
        """
        Removes the index for the provided view if it is not used by any other view.

        :param view: The view to remove the index for.
        :param model: The model to use for the table. If not provided it will be
            generated.
        :return: The name of the index for the view if any.
        """

        current_index_name = view.db_index_name
        if not current_index_name:
            return None

        other_view_using_index = View.objects.filter(
            db_index_name=current_index_name, table=view.table
        ).exclude(pk=view.pk)

        db_index = django_models.Index("id", name=current_index_name)

        if other_view_using_index.exists() or not cls.does_index_exist(
            current_index_name
        ):
            return current_index_name

        cls.drop_index(view, db_index, model)

        return current_index_name

    @classmethod
    def drop_index(cls, view, db_index, model=None):
        if model is None:
            model = view.table.get_model()

        with safe_django_schema_editor() as schema_editor:
            schema_editor.remove_index(model, db_index)
            logger.info(
                "Removed Index {db_index_name} for view {view_pk} of table {view_table_id}",
                db_index_name=db_index.name,
                view_pk=view.pk,
                view_table_id=view.table_id,
            )

    @classmethod
    def update_index_by_view_id(cls, view_id: int, nowait=True):
        """
        Updates the index for the view with the provided id. If the view has been
        trashed, a ViewDoesNotExist exception will be raised. If nowait is set to True,
        the operation will not wait for a lock on the table, raising a DatabaseError if
        the lock cannot be acquired immediately.

        :param view_id: The id of the view to update the index for.
        :param nowait: If set to True, the operation will not wait for a lock on the
            table, raising a DatabaseError if the lock cannot be acquired immediately
        :raises ViewDoesNotExist: When the view with the provided id does not exist.
        :raises DatabaseError: When the lock on the table cannot be acquired
            immediately.
        """

        view = ViewHandler().get_view(
            view_id,
            base_queryset=View.objects.select_related("table").prefetch_related(
                "viewsort_set", "viewgroupby_set"
            ),
        )

        # Let's immediately try to get a lock on the table with the NOWAIT option. If
        # we can't get the lock, we don't want to queue this operation, but rather
        # retry it in a few seconds.
        if nowait:
            first_sql_to_run = (
                sql.SQL("LOCK TABLE {0} IN SHARE MODE NOWAIT"),
                [sql.Identifier(view.table.get_database_table_name())],
            )
        else:
            first_sql_to_run = None

        with transaction_atomic(
            first_sql_to_run_in_transaction_with_args=first_sql_to_run
        ):
            ViewIndexingHandler.update_index(view)

    @classmethod
    def update_index(cls, view: View, model: Optional[GeneratedTableModel] = None):
        """
        Updates the index for the provided view. If the view has been trashed,
        it will just delete the current index if no other view is using it. If
        the view is not trashed, it will first delete the old index if exists
        and no other view is using it and then create the new one if missing.

        :param view: The view to update the index for.
        :param model: The model to use for the table. If not provided the model
            will be generated.
        """

        with atomic_if_not_already():
            if model is None:
                model = view.table.get_model()

            db_index = cls.get_index(view, model)
            new_index_name = db_index and db_index.name
            if view.db_index_name == new_index_name:
                return  # Nothing to do, the index is already up to date.

            # remove the previous and create the new index
            cls.drop_index_if_unused(view, model)
            if db_index is not None:
                cls.create_index_if_not_exists(view, model, db_index)

            view.db_index_name = new_index_name
            view.save(update_fields=["db_index_name"])


class ViewHandler(metaclass=baserow_trace_methods(tracer)):
    PUBLIC_VIEW_TOKEN_ALGORITHM = "HS256"  # nosec

    def list_views(
        self,
        user: AbstractUser,
        table: Table,
        _type: str | None = None,
        filters: bool = True,
        sortings: bool = True,
        decorations: bool = True,
        group_bys: bool = True,
        limit: int | None = None,
    ) -> Iterable[View]:
        """
        Lists available views for a user/table combination.

        :user: The user on whose behalf we want to return views.
        :table: The table for which the views should be returned.
        :_type: The view type to get.
        :filters: If filters should be prefetched.
        :sortings: If sorts should be prefetched.
        :decorations: If view decorations should be prefetched.
        :limit: To limit the number of returned views.
        :return: Iterator over returned views.
        """

        views = View.objects.filter(table=table)

        views = CoreHandler().filter_queryset(
            user,
            ListViewsOperationType.type,
            views,
            table.database.workspace,
        )
        views = views.select_related(
            "content_type", "table", "table__database__workspace"
        )

        if _type:
            view_type = view_type_registry.get(_type)
            content_type = ContentType.objects.get_for_model(view_type.model_class)
            views = views.filter(content_type=content_type)

        if filters:
            views = views.prefetch_related("viewfilter_set", "filter_groups")

        if sortings:
            views = views.prefetch_related("viewsort_set")

        if decorations:
            views = views.prefetch_related("viewdecoration_set")

        if group_bys:
            views = views.prefetch_related("viewgroupby_set")

        if limit:
            views = views[:limit]

        views = specific_iterator(
            views,
            per_content_type_queryset_hook=(
                lambda model, queryset: view_type_registry.get_by_model(
                    model
                ).enhance_queryset(queryset)
            ),
        )

        return views

    def before_field_type_change(self, field: Field):
        """
        Allow trigger custom logic before field is changed.
        By default it calls ViewIndexingHandler.before_field_type_change.

        :param field: The field that is being changed.
        """

        ViewIndexingHandler.before_field_type_change(field)

    def list_workspace_views(
        self,
        user: AbstractUser,
        workspace: Workspace,
        filters: bool = False,
        sortings: bool = False,
        decorations: bool = False,
        group_bys: bool = False,
        limit: int = None,
        specific: bool = True,
        base_queryset: QuerySet = None,
    ) -> Iterable[View]:
        """
        Lists available views for a user/workspace combination.

        :user: The user on whose behalf we want to return views.
        :workspace: The workspace for which the views should be returned.
        :filters: If filters should be prefetched.
        :sortings: If sorts should be prefetched.
        :decorations: If view decorations should be prefetched.
        :limit: To limit the number of returned views.
        :specific: set `True` to return specific instances.
        :base_queryset: specify a base queryset to use.
        :return: Iterator over returned views.
        """

        views = base_queryset if base_queryset else View.objects.all()

        views = views.filter(table__database__workspace=workspace)

        views = views.select_related(
            "table", "table__database", "table__database__workspace"
        )

        if filters:
            views = views.prefetch_related("viewfilter_set", "filter_groups")

        if sortings:
            views = views.prefetch_related("viewsort_set")

        if decorations:
            views = views.prefetch_related("viewdecoration_set")

        if group_bys:
            views = views.prefetch_related("viewgroupby_set")

        if limit:
            views = views[:limit]

        views = CoreHandler().filter_queryset(
            user,
            ListViewsOperationType.type,
            views,
            workspace,
        )

        if specific:
            views = views.select_related("content_type")
            return specific_iterator(
                views,
                per_content_type_queryset_hook=(
                    lambda model, queryset: view_type_registry.get_by_model(
                        model
                    ).enhance_queryset(queryset)
                ),
            )

        return views

    def get_view_as_user(
        self,
        user: AbstractUser,
        view_id: int,
        view_model: Optional[Type[View]] = None,
        base_queryset: Optional[QuerySet] = None,
        table_id: Optional[int] = None,
    ) -> View:
        """
        Selects a view and checks if the user has access to that view.
        If everything is fine the view is returned.

        :param user: User on whose behalf to get the view.
        :param view_id: The identifier of the view that must be returned.
        :param view_model: If provided that models objects are used to select the
            view. This can for example be useful when you want to select a GridView or
            other child of the View model.
        :param base_queryset: The base queryset from where to select the view
            object. This can for example be used to do a `select_related`. Note that
            if this is used the `view_model` parameter doesn't work anymore.
        :params table_id: The table id of the view. This is used to check if the
            view is in the table. If not provided the view is not checked.
        :raises ViewDoesNotExist: When the view with the provided id does not exist.
        :raises PermissionDenied: When not allowed.
        :return: the view instance.
        """

        view = self.get_view(view_id, view_model, base_queryset, table_id=table_id)
        CoreHandler().check_permissions(
            user,
            ReadViewOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
        )
        return view

    def get_view(
        self,
        view_id: int | str,
        view_model: Optional[Type[View]] = None,
        base_queryset: Optional[QuerySet] = None,
        table_id: Optional[int] = None,
        pk_field: str = "pk",
    ) -> View:
        """
        Selects a view and checks if the user has access to that view.
        If everything is fine the view is returned.

        :param view_id: The identifier of the view that must be returned. By default
            it's primary key value, but `pk_field` param allows to query by another
            unique field.
        :param view_model: If provided that models objects are used to select the
            view. This can for example be useful when you want to select a GridView or
            other child of the View model.
        :param base_queryset: The base queryset from where to select the view
            object. This can for example be used to do a `select_related`. Note that
            if this is used the `view_model` parameter doesn't work anymore.
        :params table_id: The table id of the view. This is used to check if the
            view is in the table. If not provided the view is not checked.
        :param pk_field: name of unique field to query for `view_id` value.
            `'pk'` by default,
        :raises ViewDoesNotExist: When the view with the provided id does not exist.
        :return: the view instance.
        """

        if view_model is None:
            view_model = View

        if base_queryset is None:
            base_queryset = view_model.objects.all()

        try:
            view = base_queryset.select_related("table__database__workspace").get(
                **{pk_field: view_id}
            )
        except View.DoesNotExist as exc:
            raise ViewDoesNotExist(
                f"The view with id {view_id} does not exist."
            ) from exc

        if table_id is not None and view.table_id != table_id:
            raise ViewDoesNotExist(f"The view with id {view_id} does not exist.")

        if TrashHandler.item_has_a_trashed_parent(view.table, check_item_also=True):
            raise ViewDoesNotExist(f"The view with id {view_id} does not exist.")

        return view

    def get_view_for_update(
        self,
        user: AbstractUser,
        view_id: int,
        view_model: Optional[Type[View]] = None,
        base_queryset: Optional[QuerySet] = None,
    ) -> View:
        """
        Selects a view for update and checks if the user has access to that view.
        If everything is fine the view is returned.

        :param: User on whose behalf to get the view.
        :param view_id: The identifier of the view that must be returned.
        :param view_model: If provided that models objects are used to select the
            view. This can for example be useful when you want to select a GridView or
            other child of the View model.
        :param base_queryset: The base queryset from where to select the view
            object. This can for example be used to do a `select_related`. Note that
            if this is used the `view_model` parameter doesn't work anymore.
        :raises ViewDoesNotExist: When the view with the provided id does not exist.
        :return: the view instance.
        """

        if view_model is None:
            view_model = View

        if base_queryset is None:
            tables_to_lock = ("self",)
            if view_model is not View:
                # We are a specific type of View like a GalleryView, make sure to lock
                # the row in the View table by adding the `view_ptr_id`.
                tables_to_lock = ("self", "view_ptr_id")
            base_queryset = view_model.objects.select_for_update(of=tables_to_lock)

        return self.get_view_as_user(user, view_id, view_model, base_queryset)

    def create_view(
        self, user: AbstractUser, table: Table, type_name: str, **kwargs
    ) -> View:
        """
        Creates a new view based on the provided type.

        :param user: The user on whose behalf the view is created.
        :param table: The table that the view instance belongs to.
        :param type_name: The type name of the view.
        :param kwargs: The fields that need to be set upon creation.
        :raises PermissionDenied: When not allowed.
        :raises ViewOwnershipTypeDoesNotExist: When the provided
            view ownership type in kwargs doesn't exist.
        :return: The created view instance.
        """

        view_ownership_type_str = kwargs.get(
            "ownership_type", OWNERSHIP_TYPE_COLLABORATIVE
        )
        view_ownership_type = view_ownership_type_registry.get(view_ownership_type_str)
        view_type = view_type_registry.get(type_name)

        workspace = table.database.workspace

        CoreHandler().check_permissions(
            user,
            view_ownership_type.get_operation_to_check_to_create_view().type,
            workspace=workspace,
            context=table,
        )
        view_type.before_view_create(kwargs, table, user)

        model_class = view_type.model_class
        view_values = view_type.prepare_values(kwargs, table, user)

        allowed_fields = [
            "name",
            "ownership_type",
            "filter_type",
            "filters_disabled",
        ] + view_type.allowed_fields
        view_values = extract_allowed(view_values, allowed_fields)
        last_order = model_class.get_last_order(table)

        instance = model_class.objects.create(
            table=table, order=last_order, owned_by=user, **view_values
        )

        if instance.public:
            CoreHandler().check_permissions(
                user,
                CreatePublicViewOperationType.type,
                workspace=workspace,
                context=table,
            )

        view_type.view_created(view=instance)
        view_ownership_type.view_created(user=user, view=instance, workspace=workspace)
        view_created.send(self, view=instance, user=user, type_name=type_name)

        return instance

    def find_unused_view_name(self, table_id: int, proposed_name: str) -> str:
        """
        Finds an unused name for a view.

        :param table_id: The table_id of the view.
        :param proposed_name: The name that is proposed to be used.
        :return: A new unique name to use.
        """

        existing_view_names = View.objects.filter(table_id=table_id).values_list(
            "name", flat=True
        )
        return find_unused_name([proposed_name], existing_view_names, max_length=255)

    def duplicate_view(self, user: AbstractUser, original_view: View) -> View:
        """
        Duplicates the given view to create a new one. The name is appended with the
        copy number and if the original view is publicly shared, the created view
        will not be shared anymore. The new view will be created just after the original
        view.

        :param user: The user whose ask for the duplication.
        :param original_view: The original view to be duplicated.
        :return: The created view instance.
        """

        workspace = original_view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            DuplicateViewOperationType.type,
            workspace=workspace,
            context=original_view,
        )

        view_type = view_type_registry.get_by_model(original_view)

        config = ImportExportConfig(
            include_permission_data=True,
            reduce_disk_space_usage=False,
            is_duplicate=True,
        )

        cache = {
            "workspace_id": workspace.id,
        }

        # Use export/import to duplicate the view easily
        serialized = view_type.export_serialized(original_view, config, cache)

        # Change the name of the view
        serialized["name"] = self.find_unused_view_name(
            original_view.table_id, serialized["name"]
        )

        # The new view must not be publicly shared
        if "public" in serialized:
            serialized["public"] = False

        # We don't want to export the db_index_name, but if it has been create,
        # the new view can reference it.
        serialized["db_index_name"] = original_view.db_index_name

        # We're using the MirrorDict here because the fields and select options in
        # the mapping remain the same. They haven't change because we're only
        # reimporting the view and not the table, fields, etc.
        id_mapping = {
            "workspace_id": workspace.id,
            "database_fields": MirrorDict(),
            "database_field_select_options": MirrorDict(),
        }
        duplicated_view = view_type.import_serialized(
            original_view.table, serialized, config, id_mapping
        )

        if duplicated_view is None:
            # Somehow the user tried to duplicate a view they are not allowed to see
            # due to the views ownership type. Tell them the view does not exist as it
            # should not from their POV.
            raise ViewDoesNotExist()

        # We want to order views from the same table with the same ownership_type only
        queryset = View.objects.filter(
            table_id=original_view.table.id, ownership_type=original_view.ownership_type
        )
        view_ids = queryset.values_list("id", flat=True)

        ordered_ids = []
        for view_id in view_ids:
            if view_id != duplicated_view.id:
                ordered_ids.append(view_id)
            if view_id == original_view.id:
                ordered_ids.append(duplicated_view.id)

        full_order = View.order_objects(queryset, ordered_ids)
        duplicated_view.refresh_from_db()

        view_created.send(
            self, view=duplicated_view, user=user, type_name=view_type.type
        )
        views_reordered.send(
            self,
            table=original_view.table,
            order=full_order,
            user=user,
        )

        return duplicated_view

    def update_view(
        self, user: AbstractUser, view: View, **data: Dict[str, Any]
    ) -> UpdatedViewWithChangedAttributes:
        """
        Updates an existing view instance.

        :param user: The user on whose behalf the view is updated.
        :param view: The view instance that needs to be updated.
        :param data: The properties that need to be updated.
        :raises ValueError: When the provided view not an instance of View.
        :return: The updated view instance.
        """

        if not isinstance(view, View):
            raise ValueError("The view is not an instance of View.")

        view_type = view_type_registry.get_by_model(view)
        view_type.check_view_update_permissions(user, view, data)
        view_type.before_view_update(data, view, user)

        old_view = deepcopy(view)

        view_values = view_type.prepare_values(data, view.table, user)
        allowed_fields = [
            "name",
            "filter_type",
            "filters_disabled",
            "public_view_password",
            "show_logo",
            "allow_public_export",
        ] + view_type.allowed_fields

        changed_allowed_keys = set(extract_allowed(view_values, allowed_fields).keys())
        original_view_values = self._get_prepared_values_for_data(
            view_type, view, changed_allowed_keys
        )

        ownership_type_key = "ownership_type"
        new_ownership_type = view_values.get(ownership_type_key, None)
        original_ownership_type = getattr(view, ownership_type_key)
        if (
            new_ownership_type is not None
            and new_ownership_type != original_ownership_type
        ):
            try:
                ownership_type = view_ownership_type_registry.get(new_ownership_type)
            except ViewOwnershipTypeDoesNotExist:
                raise PermissionDenied()

            view = ownership_type.change_ownership_type(user, view)

            # Add the change of ownership type to the tracked changes for undo/redo
            original_view_values[ownership_type_key] = original_ownership_type
            changed_allowed_keys.add(ownership_type_key)

        previous_public_value = view.public
        allowed_attrs, allowed_m2m_fields = split_attrs_and_m2m_fields(
            allowed_fields, view
        )
        view = set_allowed_attrs(view_values, allowed_attrs, view)
        if previous_public_value != view.public:
            workspace = view.table.database.workspace
            CoreHandler().check_permissions(
                user,
                UpdateViewPublicOperationType.type,
                workspace=workspace,
                context=view,
            )

        view.save()
        view = set_allowed_m2m_fields(view_values, allowed_m2m_fields, view)

        new_view_values = self._get_prepared_values_for_data(
            view_type, view, changed_allowed_keys
        )

        if "filters_disabled" in view_values:
            view_type.after_filter_update(view)

        view_updated.send(self, view=view, user=user, old_view=old_view)

        return UpdatedViewWithChangedAttributes(
            updated_view_instance=view,
            original_view_attributes=original_view_values,
            new_view_attributes=new_view_values,
        )

    def order_views(self, user: AbstractUser, table: Table, order: List[int]):
        """
        Updates the order of the views in the given table. The order of the views
        that are not in the `order` parameter set to `0`.

        :param user: The user on whose behalf the views are ordered.
        :param table: The table of which the views must be updated.
        :param order: A list containing the view ids in the desired order.
        :raises ViewNotInTable: If one of the view ids in the order does not belong
            to the table.
        """

        workspace = table.database.workspace
        CoreHandler().check_permissions(
            user, OrderViewsOperationType.type, workspace=workspace, context=table
        )

        try:
            first_view = self.get_view(order[0])
        except ViewDoesNotExist:
            raise ViewNotInTable()

        all_views = View.objects.filter(table_id=table.id).filter(
            ownership_type=first_view.ownership_type
        )

        user_views = CoreHandler().filter_queryset(
            user,
            ListViewsOperationType.type,
            all_views,
            workspace=workspace,
        )

        view_ids = user_views.values_list("id", flat=True)

        for view_id in order:
            if view_id not in view_ids:
                raise ViewNotInTable(view_id)

        full_order = View.order_objects(user_views, order)
        views_reordered.send(
            self,
            table=table,
            order=full_order,
            user=user,
        )

    def get_views_order(self, user: AbstractUser, table: Table, ownership_type: str):
        """
        Returns the order of the views in the given table.

        :param user: The user on whose behalf the views are ordered.
        :param table: The table of which the views must be updated.
        :param ownership_type: The type of views for which to return the order.
        :raises ViewNotInTable: If one of the view ids in the order does not belong
            to the table.
        """

        workspace = table.database.workspace
        if ownership_type is None:
            ownership_type = OWNERSHIP_TYPE_COLLABORATIVE

        CoreHandler().check_permissions(
            user, ReadViewsOrderOperationType.type, workspace=workspace, context=table
        )

        queryset = View.objects.filter(table_id=table.id).filter(
            ownership_type=ownership_type
        )
        queryset = CoreHandler().filter_queryset(
            user,
            ListViewsOperationType.type,
            queryset,
            table.database.workspace,
        )

        order = queryset.values_list("id", flat=True)
        order = list(order)

        return order

    def delete_view_by_id(self, user: AbstractUser, view_id: int):
        """
        Trashes an existing view instance.

        :param user: The user on whose behalf the view is deleted.
        :param view_id: The view instance id that needs to be deleted.
        """

        view = self.get_view_for_update(user, view_id)
        self.delete_view(user, view)

    def delete_view(self, user: AbstractUser, view: View):
        """
        Trashes an existing view instance.

        :param user: The user on whose behalf the view is deleted.
        :param view: The view instance that needs to be deleted.
        :raises ViewDoesNotExist: When the view with the provided id does not exist.
        """

        if not isinstance(view, View):
            raise ValueError("The view is not an instance of View")

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            user, DeleteViewOperationType.type, workspace=workspace, context=view
        )

        view_id = view.id

        TrashHandler().trash(user, workspace, view.table.database, view)

        view_deleted.send(self, view_id=view_id, view=view, user=user)

    def get_field_options_as_user(self, user: AbstractUser, view: View):
        """
        Returns a serializer class to get field options stored for the view.

        :param user: The user on whose behalf the options are requested.
        :param view: The view for which the options should be returned.
        :returns: View type that has get_field_options_serializer_class().
        """

        workspace = view.table.database.workspace

        CoreHandler().check_permissions(
            user,
            ReadViewFieldOptionsOperationType.type,
            workspace=workspace,
            context=view,
        )
        view_type = view_type_registry.get_by_model(view)
        return view_type

    def update_field_options(
        self,
        view: View,
        field_options: FieldOptionsDict,
        user: Optional[AbstractUser] = None,
        fields: Optional[QuerySet[Field]] = None,
    ):
        """
        Updates the field options with the provided values if the field id exists in
        the table related to the view.

        This will also update views which are trashed. It is up to the caller to
        ensure that the view is not trashed if they would like to exclude it from
        the update.

        It is necessary to do so, because aggregations have to be removed
        from trashed views as well if the field options change. Otherwise,
        you might restore a view and the aggregation is invalid on that view.

        :param view: The view for which the field options need to be updated.
        :param field_options: A dict with the field ids as the key and a dict
            containing the values that need to be updated as value.
        :param user: Optionally the user on whose behalf the request is made. If you
          give a user, the permissions are checked against this user otherwise there is
          no permission checking.
        :param fields: Optionally a list of fields can be provided so that they don't
            have to be fetched again.
        :raises UnrelatedFieldError: When the provided field id is not related to the
            provided view.
        """

        if user is not None:
            # Here we check the permissions only if we have a user. If the field options
            # update is triggered by user a action, we have one from the view but in
            # some situation, we have automatic processing and we don't have any user.
            CoreHandler().check_permissions(
                user,
                UpdateViewFieldOptionsOperationType.type,
                workspace=view.table.database.workspace,
                context=view,
            )

        if not fields:
            fields = Field.objects.filter(table=view.table)

        try:
            model = view._meta.get_field("field_options").remote_field.through
        except FieldDoesNotExist as exc:
            raise ViewDoesNotSupportFieldOptions(
                "This view does not support field options."
            ) from exc

        field_name = get_model_reference_field_name(model, View)

        if not field_name:
            raise ValueError(
                "The model doesn't have a relationship with the View model or any "
                "descendants."
            )

        view_type = view_type_registry.get_by_model(view.specific_class)
        field_options = view_type.before_field_options_update(
            view, field_options, fields
        )

        # Figure out which field options can be updated and fetch existing ones. We
        # need the existing ones to later determine whether it must be updated or
        # newly created.
        allowed_field_ids = [field.id for field in fields]
        valid_field_ids = []
        for field_id, options in field_options.items():
            if int(field_id) not in allowed_field_ids:
                raise UnrelatedFieldError(
                    f"The field id {field_id} is not related to the view."
                )
            valid_field_ids.append(field_id)

        existing_field_options = {
            o.field_id: o
            for o in model.objects_and_trash.filter(
                field_id__in=valid_field_ids, **{field_name: view}
            ).select_for_update(of=("self",))
        }

        field_options_to_create = []
        field_options_to_update = []
        option_names_to_update = set()

        for field_id, options in field_options.items():
            exists = int(field_id) in existing_field_options

            if exists:
                field_options_object = existing_field_options[int(field_id)]
            else:
                field_options_object = view_type.prepare_field_options(view, field_id)

            allowed_values = extract_allowed(
                options, view_type.field_options_allowed_fields
            )
            for key, value in allowed_values.items():
                setattr(field_options_object, key, value)
                option_names_to_update.add(key)

            if exists:
                field_options_to_update.append(field_options_object)
            else:
                field_options_to_create.append(field_options_object)

        if len(field_options_to_create) > 0:
            model.objects_and_trash.bulk_create(
                field_options_to_create, ignore_conflicts=True
            )

        if len(field_options_to_update) > 0 and len(option_names_to_update) > 0:
            model.objects_and_trash.bulk_update(
                field_options_to_update, option_names_to_update
            )

        updated_instances = field_options_to_create + field_options_to_update
        view_type.after_field_options_update(
            view, field_options, fields, updated_instances
        )

        view_field_options_updated.send(self, view=view, user=user)

    def after_field_moved_between_tables(self, field: Field, original_table_id: int):
        """
        This method is called to properly update the view field options when a field
        is moved between tables.

        :param field: The new field object.
        :param original_table_id: The id of the table where the field was moved from.
        """

        for view_type in view_type_registry.get_all():
            view_type.after_field_moved_between_tables(field, original_table_id)

    def fields_type_changed(self, fields: List[Field]):
        """
        This method is called by the FieldHandler when the field type of a field has
        changed. It could be that the field has filters, sortings, or other view
        related things are not compatible anymore. If that is the case then those
        need to be removed. All view_type `after_field_type_change` of views that are
        linked to this field are also called to react on this change.

        It's recommended to call this method in bulk instead of for every changed
        field individually because it's not query efficient that way.

        :param fields: The fields that have changed.
        """

        if len(fields) == 0:
            return

        # Keep track of the changed fields so that the
        # `after_fields_changed_or_deleted` can be called in bulk and make it query
        # efficient.
        changed_fields = set()
        all_fields_mapping = {field.id: field for field in fields}

        # Fetch the sorts of all updated fields to check if the sort, including the
        # type, is still compatible.
        sorts_to_check = ViewSort.objects.filter(field_id__in=all_fields_mapping.keys())
        fields_to_delete_sortings = [
            all_fields_mapping[sort.field_id]
            for sort in sorts_to_check
            if not field_type_registry.get_by_model(
                all_fields_mapping[sort.field_id].specific_class
            ).check_can_order_by(all_fields_mapping[sort.field_id], sort.type)
        ]

        # If it's a primary field, we also need to remove any sortings on the
        # link row fields pointing to this table.
        primary_fields_table_ids = [
            field.table_id for field in fields_to_delete_sortings if field.primary
        ]
        if len(primary_fields_table_ids) > 0:
            related_fields = LinkRowField.objects.filter(
                link_row_table_id__in=primary_fields_table_ids
            )
            fields_to_delete_sortings += list(related_fields)

        if fields_to_delete_sortings:
            deleted_count, _ = ViewSort.objects.filter(
                field_id__in=[field.id for field in fields_to_delete_sortings]
            ).delete()
            if deleted_count > 0:
                changed_fields.update(fields_to_delete_sortings)

        # Fetch the group bys of all updated fields to check if the group by, including
        # the type, is still compatible.
        groups_to_check = ViewGroupBy.objects.filter(
            field_id__in=all_fields_mapping.keys()
        )
        fields_to_delete_groupings = [
            all_fields_mapping[sort.field_id]
            for sort in groups_to_check
            if not field_type_registry.get_by_model(
                all_fields_mapping[sort.field_id].specific_class
            ).check_can_group_by(all_fields_mapping[sort.field_id], sort.type)
        ]
        if fields_to_delete_groupings:
            deleted_count, _ = ViewGroupBy.objects.filter(
                field_id__in=[field.id for field in fields_to_delete_groupings]
            ).delete()
            if deleted_count > 0:
                changed_fields.update(fields_to_delete_sortings)

        if len(changed_fields) > 0:
            ViewIndexingHandler.after_fields_changed_or_deleted(list(changed_fields))

        filters_to_check = ViewFilter.objects.filter(
            field_id__in=[f.id for f in fields]
        ).select_related("field")
        incompatible_filter_ids = [
            filter.id
            for filter in filters_to_check
            if not view_filter_type_registry.get(filter.type).field_is_compatible(
                filter.field
            )
        ]
        if len(incompatible_filter_ids) > 0:
            ViewFilter.objects.filter(id__in=incompatible_filter_ids).delete()

        # Call view types hook
        for view_type in view_type_registry.get_all():
            view_type.after_fields_type_change(fields)

        for (
            decorator_value_provider_type
        ) in decorator_value_provider_type_registry.get_all():
            decorator_value_provider_type.after_fields_type_change(fields)

    def field_value_updated(self, updated_fields: Union[Iterable[Field], Field]):
        """
        Called after a field value has been modified because of a row creation,
        modification, deletion. This method is called for each directly or indirectly
        affected list of fields.

        Calls the `.after_field_value_update(updated_fields)` of each view type.

        :param updated_fields: The field or list of fields that are affected.
        """

        if not isinstance(updated_fields, list):
            updated_fields = [updated_fields]

        # Call each view types hook
        for view_type in view_type_registry.get_all():
            view_type.after_field_value_update(updated_fields)

    def field_updated(self, updated_fields: Union[Iterable[Field], Field]):
        """
        Called for each field modification. This include indirect modification when
        fields depends from another (like formula fields or lookup fields).

        Calls the `.after_field_update(updated_fields)` of each view type.

        :param updated_fields: The field or list of fields that are updated.
        """

        if not isinstance(updated_fields, list):
            updated_fields = [updated_fields]

        # Call each view types hook
        for view_type in view_type_registry.get_all():
            view_type.after_field_update(updated_fields)

        for field in updated_fields:
            field_type = field_type_registry.get_by_model(field.specific_class)
            # Check whether the updated field is still compatible with the group by.
            # If not, it must be deleted.
            if not field_type.check_can_group_by(field, DEFAULT_SORT_TYPE_KEY):
                ViewGroupBy.objects.filter(field=field).delete()

    def get_filter_builder(
        self, view: View, model: Type[GeneratedTableModel]
    ) -> FilterBuilder:
        """
        Constructs a FilterBuilder object based on the provided view's filter.

        :param view: The view where to fetch the fields from.
        :param model: The generated model containing all fields.
        :return: FilterBuilder object with the view's filter applied.
        """

        # The table model has to be dynamically generated
        if not hasattr(model, "_field_objects"):
            raise ValueError("A queryset of the table model is required.")

        adapter = ViewGroupedFiltersAdapter(view, model)
        return AdvancedFilterBuilder(adapter).construct_filter_builder()

    def apply_filters(self, view: View, queryset: QuerySet) -> QuerySet:
        """
        Applies the view's filter to the given queryset.

        :param view: The view where to fetch the fields from.
        :param queryset: The queryset where the filters need to be applied to.
        :raises ValueError: When the queryset's model is not a table model or if the
            table model does not contain the one of the fields.
        :return: The queryset where the filters have been applied to.
        """

        model = queryset.model

        if view.filters_disabled:
            return queryset

        filter_builder = self.get_filter_builder(view, model)
        return filter_builder.apply_to_queryset(queryset)

    def list_filters(self, user: AbstractUser, view_id: int) -> QuerySet[ViewFilter]:
        """
        Returns the ViewFilter queryset for the provided view_id.

        :param user: The user on whose behalf the filters are requested.
        :param view_id: The id of the view for which we want to return filters.
        :returns: ViewFilter queryset for the view_id.
        """

        view = self.get_view(view_id)
        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            user, ListViewFilterOperationType.type, workspace=workspace, context=view
        )
        filters = ViewFilter.objects.filter(view=view)
        return filters

    def get_filter(
        self,
        user: AbstractUser,
        view_filter_id: int,
        base_queryset: Optional[QuerySet] = None,
    ) -> ViewFilter:
        """
        Returns an existing view filter by the given id.

        :param user: The user on whose behalf the view filter is requested.
        :param view_filter_id: The id of the view filter.
        :param base_queryset: The base queryset from where to select the view filter
            object. This can for example be used to do a `select_related`.
        :raises ViewFilterDoesNotExist: The requested view does not exists.
        :return: The requested view filter instance.
        """

        if base_queryset is None:
            base_queryset = ViewFilter.objects

        try:
            view_filter = base_queryset.select_related(
                "view__table__database__workspace"
            ).get(pk=view_filter_id)
        except ViewFilter.DoesNotExist:
            raise ViewFilterDoesNotExist(
                f"The view filter with id {view_filter_id} does not exist."
            )

        if TrashHandler.item_has_a_trashed_parent(
            view_filter.view, check_item_also=True
        ):
            raise ViewFilterDoesNotExist(
                f"The view filter with id {view_filter_id} does not exist."
            )

        workspace = view_filter.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            ReadViewFilterOperationType.type,
            workspace=workspace,
            context=view_filter,
        )

        return view_filter

    def create_filter(
        self,
        user: AbstractUser,
        view: View,
        field: Field,
        type_name: str,
        value: str,
        filter_group_id: Optional[int] = None,
        primary_key: Optional[int] = None,
    ) -> ViewFilter:
        """
        Creates a new view filter. The rows that are visible in a view should always
        be filtered by the related view filters.

        :param user: The user on whose behalf the view filter is created.
        :param view: The view for which the filter needs to be created.
        :param field: The field that the filter should compare the value with.
        :param type_name: The filter type, allowed values are the types in the
            view_filter_type_registry `equal`, `not_equal` etc.
        :param value: The value that the filter must apply to.
        :param filter_group_id: An optional filter group id to add the filter to.
        :param primary_key: An optional primary key to give to the new view filter.
        :raises ViewFilterNotSupported: When the provided view does not support
            filtering.
        :raises ViewFilterTypeNotAllowedForField: When the field does not support the
            filter type.
        :raises FieldNotInTable:  When the provided field does not belong to the
            provided view's table.
        :return: The created view filter instance.
        """

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            CreateViewFilterOperationType.type,
            workspace=workspace,
            context=view,
        )

        # Check if view supports filtering
        view_type = view_type_registry.get_by_model(view.specific_class)
        if not view_type.can_filter:
            raise ViewFilterNotSupported(
                f"Filtering is not supported for {view_type.type} views."
            )

        view_filter_type = view_filter_type_registry.get(type_name)
        field_type = field_type_registry.get_by_model(field.specific_class)

        # Check if the field is allowed for this filter type.
        if not view_filter_type.field_is_compatible(field):
            raise ViewFilterTypeNotAllowedForField(type_name, field_type.type)

        # Check if field belongs to the grid views table
        if not view.table.field_set.filter(id=field.pk).exists():
            raise FieldNotInTable(
                f"The field {field.pk} does not belong to table {view.table.id}."
            )

        if filter_group_id is not None:
            self.get_filter_group(user, filter_group_id)

        view_filter = ViewFilter.objects.create(
            pk=primary_key,
            view=view,
            field=field,
            type=view_filter_type.type,
            value=value,
            group_id=filter_group_id,
        )

        # Call view type hooks
        view_type.after_filter_update(view)

        view_filter_created.send(self, view_filter=view_filter, user=user)

        return view_filter

    def update_filter(
        self,
        user: AbstractUser,
        view_filter: ViewFilter,
        field: Field = None,
        type_name: str = None,
        value: str = None,
    ) -> ViewFilter:
        """
        Updates the values of an existing view filter.

        :param user: The user on whose behalf the view filter is updated.
        :param view_filter: The view filter that needs to be updated.
        :param field: The model of the field to filter by.
        :param type_name: Indicates how the field's value must be compared
        to the filter's value.
        :param value: The filter value that must be compared to the field's value.
        :raises ViewFilterTypeNotAllowedForField: When the field does not support the
            filter type.
        :raises FieldNotInTable: When the provided field does not belong to the
            view's table.
        :return: The updated view filter instance.
        """

        workspace = view_filter.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            UpdateViewFilterOperationType.type,
            workspace=workspace,
            context=view_filter,
        )

        type_name = type_name if type_name is not None else view_filter.type
        field = field if field is not None else view_filter.field
        value = value if value is not None else view_filter.value
        view_filter_type = view_filter_type_registry.get(type_name)
        field_type = field_type_registry.get_by_model(field.specific_class)

        # Check if the field is allowed for this filter type.
        if not view_filter_type.field_is_compatible(field):
            raise ViewFilterTypeNotAllowedForField(type_name, field_type.type)

        # If the field has changed we need to check if the field belongs to the table.
        if (
            field.id != view_filter.field_id
            and not view_filter.view.table.field_set.filter(id=field.pk).exists()
        ):
            raise FieldNotInTable(
                f"The field {field.pk} does not belong to table "
                f"{view_filter.view.table.id}."
            )

        view_filter.field = field
        view_filter.value = value
        view_filter.type = type_name
        view_filter.save()

        # Call view type hooks
        view_type = view_type_registry.get_by_model(view_filter.view.specific_class)
        view_type.after_filter_update(view_filter.view)

        view_filter_updated.send(self, view_filter=view_filter, user=user)

        return view_filter

    def delete_filter(self, user: AbstractUser, view_filter: ViewFilter):
        """
        Deletes an existing view filter.

        :param user: The user on whose behalf the view filter is deleted.
        :param view_filter: The view filter instance that needs to be deleted.
        """

        workspace = view_filter.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            DeleteViewFilterOperationType.type,
            workspace=workspace,
            context=view_filter,
        )

        view_filter_id = view_filter.id
        view_filter.delete()

        # Call view type hooks
        view_type = view_type_registry.get_by_model(view_filter.view.specific_class)
        view_type.after_filter_update(view_filter.view)

        view_filter_deleted.send(
            self, view_filter_id=view_filter_id, view_filter=view_filter, user=user
        )

    def get_filter_group(
        self,
        user: AbstractUser,
        filter_group_id: int,
        base_queryset: Optional[QuerySet] = None,
    ) -> ViewFilterGroup:
        """
        Returns an existing view filter group by the given id.

        :param user: The user on whose behalf the view filter is requested.
        :param filter_group_id: The id of the view filter group to return.
        :param base_queryset: The base queryset from where to select the view filter
            object. This can for example be used to do a `select_related`.
        :raises ViewFilterGroupDoesNotExist: The requested view does not exists.
        :return: The requested view filter group instance.
        """

        if base_queryset is None:
            base_queryset = ViewFilterGroup.objects

        try:
            filter_group = base_queryset.select_related(
                "view__table__database__workspace"
            ).get(pk=filter_group_id)
        except ViewFilterGroup.DoesNotExist:
            raise ViewFilterGroupDoesNotExist(
                f"The view filter with id {filter_group_id} does not exist."
            )

        if TrashHandler.item_has_a_trashed_parent(
            filter_group.view, check_item_also=True
        ):
            raise ViewFilterGroupDoesNotExist(
                f"The view filter group with id {filter_group_id} does not exist."
            )

        workspace = filter_group.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            ReadViewFilterGroupOperationType.type,
            workspace=workspace,
            context=filter_group,
        )

        return filter_group

    def create_filter_group(
        self,
        user: AbstractUser,
        view: View,
        filter_type: Optional[str] = None,
        parent_group_id: Optional[int] = None,
        primary_key: Optional[int] = None,
    ) -> ViewFilterGroup:
        """
        Creates a new view filter group.

        :param user: The user on whose behalf the view filter group is created.
        :param view: The view for which the filter group needs to be created.
        :param filter_type: The filter type, allowed values are the types in the
            view_group_type_registry `and`, `or`.
        :param primary_key: An optional primary key to give to the new view
            filter group. Useful to recreate a deleted view filter group with
            the previous pk.
        :return: The created view filter group instance.
        """

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            CreateViewFilterGroupOperationType.type,
            workspace=workspace,
            context=view,
        )

        attrs = {}
        if filter_type is not None:
            attrs["filter_type"] = filter_type
        if parent_group_id is not None:
            attrs["parent_group_id"] = parent_group_id

        filter_group = ViewFilterGroup.objects.create(
            pk=primary_key, view=view, **attrs
        )

        view_filter_group_created.send(self, view_filter_group=filter_group, user=user)

        return filter_group

    def update_filter_group(
        self, user: AbstractUser, filter_group: ViewFilterGroup, filter_type: str
    ) -> ViewFilterGroup:
        """
        Updates the values of an existing view filter group.

        :param user: The user on whose behalf the view filter group is updated.
        :param filter_group: The view filter group that needs to be updated.
        :param filter_type: Indicates how filters in the group must be combined.
        :return: The updated view filter group instance.
        """

        workspace = filter_group.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            UpdateViewFilterGroupOperationType.type,
            workspace=workspace,
            context=filter_group,
        )

        filter_group.filter_type = filter_type
        filter_group.save()

        view_filter_group_updated.send(self, view_filter_group=filter_group, user=user)

        return filter_group

    def delete_filter_group(self, user: AbstractUser, filter_group: ViewFilterGroup):
        """
        Deletes an existing view filter group.

        :param user: The user on whose behalf the view filter is deleted.
        :param filter_group: The view filter group instance that needs to
            be deleted.
        """

        workspace = filter_group.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            DeleteViewFilterGroupOperationType.type,
            workspace=workspace,
            context=filter_group,
        )

        filter_group_id = filter_group.id

        filter_group.delete()

        view_filter_group_deleted.send(
            self,
            view_filter_group_id=filter_group_id,
            view_filter_group=filter_group,
            user=user,
        )

    def get_view_order_bys(
        self,
        view: View,
        model: GeneratedTableModel,
        queryset: QuerySet,
        restrict_to_field_ids: Optional[Iterable[int]] = None,
    ) -> Tuple[List[OrderBy], Optional[QuerySet]]:
        """
        Responsible for return a list of OrderBy objects which a queryset
        can use to `order_by` with.

        :param view: The view where to fetch the sorting from.
        :param model: The table's generated table model.
        :param queryset: The queryset where the sorting need to be applied to.
        :param restrict_to_field_ids: Only field ids in this iterable will have their
            view sorts applied in the resulting queryset.
        :return: A tuple containing a list of zero or more OrderBy expressions,
            and optionally a queryset if one was passed to us.
        """

        order_by = []
        for view_sort_or_group_by in view.get_all_sorts(restrict_to_field_ids):
            # If the to be sort field is not present in the `_field_objects` we
            # cannot filter so we raise a ValueError.
            if view_sort_or_group_by.field_id not in model._field_objects:
                raise ValueError(
                    f"The table model does not contain "
                    f"field {view_sort_or_group_by.field_id}."
                )

            field = model._field_objects[view_sort_or_group_by.field_id]["field"]
            field_name = model._field_objects[view_sort_or_group_by.field_id]["name"]
            field_type = model._field_objects[view_sort_or_group_by.field_id]["type"]

            field_annotated_order_by = field_type.get_order(
                field,
                field_name,
                view_sort_or_group_by.order,
                view_sort_or_group_by.type,
                table_model=queryset.model,
            )
            field_annotation = field_annotated_order_by.annotation
            field_order_bys = field_annotated_order_by.order_bys

            if field_annotation is not None:
                queryset = queryset.annotate(**field_annotation)

            for fob in field_order_bys:
                order_by.append(fob)

        order_by.extend(("order", "id"))

        return order_by, queryset

    def apply_sorting(
        self,
        view: View,
        queryset: QuerySet,
        restrict_to_field_ids: Optional[Iterable[int]] = None,
    ) -> QuerySet:
        """
        Applies the view's sorting to the given queryset. The first sort, which for now
        is the first created, will always be applied first. Secondary sortings are
        going to be applied if the values of the first sort rows are the same.

        Example:

        id | field_1 | field_2
        1  | Bram    | 20
        2  | Bram    | 10
        3  | Elon    | 30

        If we are going to sort ascending on field_1 and field_2 the resulting ids are
        going to be 2, 1 and 3 in that order.

        :param view: The view where to fetch the sorting from.
        :param queryset: The queryset where the sorting need to be applied to.
        :param restrict_to_field_ids: Only field ids in this iterable will have their
            view sorts applied in the resulting queryset.
        :raises ValueError: When the queryset's model is not a table model or if the
            table model does not contain the one of the fields.
        :raises ViewSortDoesNotExist: When the view is trashed

        :return: The queryset where the sorting has been applied to.
        """

        model = queryset.model

        # If the model does not have the `_field_objects` property then it is not a
        # generated table model which is not supported.
        if not hasattr(model, "_field_objects"):
            raise ValueError("A queryset of the table model is required.")

        if view.trashed:
            raise ViewSortDoesNotExist(f"The view {view.id} is trashed.")

        order_by, queryset = self.get_view_order_bys(
            view, model, queryset, restrict_to_field_ids
        )

        queryset = queryset.order_by(*order_by)

        return queryset

    def list_sorts(self, user: AbstractUser, view_id: int) -> QuerySet[ViewSort]:
        """
        Returns the ViewSort queryset for provided view_id.

        :param user: The user on whose behalf the sorts are requested.
        :param view_id: The id of the view for which to return sorts.
        :return: ViewSort queryset of the view's sorts.
        """

        view = ViewHandler().get_view(view_id)
        CoreHandler().check_permissions(
            user,
            ListViewSortOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
        )
        sortings = ViewSort.objects.filter(view=view)
        return sortings

    def get_sort(self, user, view_sort_id, base_queryset=None):
        """
        Returns an existing view sort with the given id.

        :param user: The user on whose behalf the view sort is requested.
        :type user: User
        :param view_sort_id: The id of the view sort.
        :type view_sort_id: int
        :param base_queryset: The base queryset from where to select the view sort
            object from. This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises ViewSortDoesNotExist: The requested view does not exists.
        :return: The requested view sort instance.
        :type: ViewSort
        """

        if base_queryset is None:
            base_queryset = ViewSort.objects

        try:
            view_sort = base_queryset.select_related(
                "view__table__database__workspace"
            ).get(pk=view_sort_id)
        except ViewSort.DoesNotExist:
            raise ViewSortDoesNotExist(
                f"The view sort with id {view_sort_id} does not exist."
            )

        if TrashHandler.item_has_a_trashed_parent(view_sort.view, check_item_also=True):
            raise ViewSortDoesNotExist(
                f"The view sort with id {view_sort_id} does not exist."
            )

        workspace = view_sort.view.table.database.workspace
        CoreHandler().check_permissions(
            user, ReadViewSortOperationType.type, workspace=workspace, context=view_sort
        )

        return view_sort

    def create_sort(
        self,
        user: AbstractUser,
        view: View,
        field: Field,
        order: str,
        primary_key: Optional[int] = None,
        sort_type: Optional[str] = None,
    ) -> ViewSort:
        """
        Creates a new view sort.

        :param user: The user on whose behalf the view sort is created.
        :param view: The view for which the sort needs to be created.
        :param field: The field that needs to be sorted.
        :param order: The desired order, can either be ascending (A to Z) or
            descending (Z to A).
        :param primary_key: An optional primary key to give to the new view sort.
        :param sort_type: The sort type that must be used, `default` is set as default
            when the sort is created.
        :raises ViewSortNotSupported: When the provided view does not support sorting.
        :raises FieldNotInTable:  When the provided field does not belong to the
            provided view's table.
        :return: The created view sort instance.
        """

        field = field.specific

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            user, ReadFieldOperationType.type, workspace=workspace, context=field
        )
        CoreHandler().check_permissions(
            user, CreateViewSortOperationType.type, workspace=workspace, context=view
        )

        if not sort_type:
            sort_type = DEFAULT_SORT_TYPE_KEY

        # Check if view supports sorting.
        view_type = view_type_registry.get_by_model(view.specific_class)
        if not view_type.can_sort:
            raise ViewSortNotSupported(
                f"Sorting is not supported for {view_type.type} views."
            )

        # Check if the field supports sorting.
        field_type = field_type_registry.get_by_model(field.specific_class)
        if not field_type.check_can_order_by(field, sort_type):
            raise ViewSortFieldNotSupported(
                f"The field {field.pk} does not support sorting with type {sort_type}."
            )

        # Check if field belongs to the grid views table
        if not view.table.field_set.filter(id=field.pk).exists():
            raise FieldNotInTable(
                f"The field {field.pk} does not belong to table {view.table.id}."
            )

        # Check if the field already exists as sort
        if view.viewsort_set.filter(field_id=field.pk).exists():
            raise ViewSortFieldAlreadyExist(
                f"A sort with the field {field.pk} already exists."
            )

        view_sort = ViewSort.objects.create(
            pk=primary_key,
            view=view,
            field=field,
            order=order,
            type=sort_type,
        )

        view_sort_created.send(self, view_sort=view_sort, user=user)

        return view_sort

    def update_sort(
        self,
        user: AbstractUser,
        view_sort: ViewSort,
        field: Optional[Field] = None,
        order: Optional[str] = None,
        sort_type: Optional[str] = None,
    ) -> ViewSort:
        """
        Updates the values of an existing view sort.

        :param user: The user on whose behalf the view sort is updated.
        :param view_sort: The view sort that needs to be updated.
        :param field: The field that must be sorted on.
        :param order: Indicates the sort order direction.
        :raises ViewSortDoesNotExist: When the view used by the filter is trashed.
        :raises ViewSortFieldNotSupported: When the field does not support sorting.
        :raises FieldNotInTable:  When the provided field does not belong to the
            provided view's table.
        :return: The updated view sort instance.
        """

        if view_sort.view.trashed:
            raise ViewSortDoesNotExist(f"The view {view_sort.view.id} is trashed.")

        workspace = view_sort.view.table.database.workspace
        field = field if field is not None else view_sort.field
        order = order if order is not None else view_sort.order
        sort_type = sort_type if sort_type is not None else view_sort.type

        CoreHandler().check_permissions(
            user, ReadFieldOperationType.type, workspace=workspace, context=field
        )
        CoreHandler().check_permissions(
            user,
            UpdateViewSortOperationType.type,
            workspace=workspace,
            context=view_sort,
        )

        # If the field has changed we need to check if the field belongs to the table.
        if (
            field.id != view_sort.field_id
            and not view_sort.view.table.field_set.filter(id=field.pk).exists()
        ):
            raise FieldNotInTable(
                f"The field {field.pk} does not belong to table "
                f"{view_sort.view.table.id}."
            )

        # If the field has changed we need to check if the new field type supports
        # sorting.
        field_type = field_type_registry.get_by_model(field.specific_class)
        if (
            field.id != view_sort.field_id or sort_type != view_sort.type
        ) and not field_type.check_can_order_by(
            field,
            sort_type,
        ):
            raise ViewSortFieldNotSupported(
                f"The field {field.pk} does not support sorting."
            )

        # If the field has changed we need to check if the new field doesn't already
        # exist as sort.
        if (
            field.id != view_sort.field_id
            and view_sort.view.viewsort_set.filter(field_id=field.pk).exists()
        ):
            raise ViewSortFieldAlreadyExist(
                f"A sort with the field {field.pk} already exists."
            )

        view_sort.field = field
        view_sort.order = order
        view_sort.type = sort_type
        view_sort.save()

        view_sort_updated.send(self, view_sort=view_sort, user=user)

        return view_sort

    def delete_sort(self, user, view_sort):
        """
        Deletes an existing view sort.

        :param user: The user on whose behalf the view sort is deleted.
        :type user: User
        :param view_sort: The view sort instance that needs to be deleted.
        :type view_sort: ViewSort
        """

        workspace = view_sort.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            DeleteViewSortOperationType.type,
            workspace=workspace,
            context=view_sort,
        )

        view_sort_id = view_sort.id
        view_sort.delete()

        view_sort_deleted.send(
            self, view_sort_id=view_sort_id, view_sort=view_sort, user=user
        )

    def list_group_bys(self, user: AbstractUser, view_id: int) -> QuerySet[ViewGroupBy]:
        """
        Returns the ViewGroupBy queryset for provided view_id.

        :param user: The user on whose behalf the group bys are requested.
        :param view_id: The id of the view for which to return group bys.
        :return: ViewGroupBy queryset of the view's group bys.
        """

        view = ViewHandler().get_view(view_id)
        CoreHandler().check_permissions(
            user,
            ListViewGroupByOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
        )
        groupings = ViewGroupBy.objects.filter(view=view)
        return groupings

    def get_group_by(self, user, view_group_by_id, base_queryset=None):
        """
        Returns an existing view group by with the given id.

        :param user: The user on whose behalf the view group by is requested.
        :type user: User
        :param view_group_by_id: The id of the view group_by.
        :type view_group_by_id: int
        :param base_queryset: The base queryset from where to select the view group
            object from. This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises ViewGroupByDoesNotExist: The requested view does not exists.
        :return: The requested view group by instance.
        :type: ViewGroupBy
        """

        if base_queryset is None:
            base_queryset = ViewGroupBy.objects

        try:
            view_group_by = base_queryset.select_related(
                "view__table__database__workspace"
            ).get(pk=view_group_by_id)
        except ViewGroupBy.DoesNotExist:
            raise ViewGroupByDoesNotExist(
                f"The view group by with id {view_group_by_id} does not exist."
            )

        if TrashHandler.item_has_a_trashed_parent(
            view_group_by.view, check_item_also=True
        ):
            raise ViewGroupByDoesNotExist(
                f"The view group by with id {view_group_by_id} does not exist."
            )

        workspace = view_group_by.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            ReadViewGroupByOperationType.type,
            workspace=workspace,
            context=view_group_by,
        )

        return view_group_by

    def create_group_by(
        self,
        user: AbstractUser,
        view: View,
        field: Field,
        order: str,
        width: int,
        sort_type: str = None,
        primary_key: Optional[int] = None,
    ) -> ViewGroupBy:
        """
        Creates a new view group_by.

        :param user: The user on whose behalf the view group by is created.
        :param view: The view for which the group by needs to be created.
        :param field: The field that needs to be grouped.
        :param order: The desired order, can either be ascending (A to Z) or
            descending (Z to A).
        :param width: The visual width of the group column.
        :param sort_type: The sort type that must be used, `default` is set as default
            when the sort is created.
        :param primary_key: An optional primary key to give to the new view group_by.
        :raises ViewGroupByNotSupported: When the provided view does not support
            grouping.
        :raises FieldNotInTable:  When the provided field does not belong to the
            provided view's table.
        :return: The created view group by instance.
        """

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            user, ReadFieldOperationType.type, workspace=workspace, context=field
        )
        CoreHandler().check_permissions(
            user, CreateViewGroupByOperationType.type, workspace=workspace, context=view
        )

        if not sort_type:
            sort_type = DEFAULT_SORT_TYPE_KEY

        # Check if view supports grouping.
        view_type = view_type_registry.get_by_model(view.specific_class)
        if not view_type.can_group_by:
            raise ViewGroupByNotSupported(
                f"Grouping is not supported for {view_type.type} views."
            )

        # Check if the field supports grouping.
        field_type = field_type_registry.get_by_model(field.specific_class)
        if not field_type.check_can_group_by(field, sort_type):
            raise ViewGroupByFieldNotSupported(
                f"The field {field.pk} does not support grouping with type {sort_type}."
            )

        # Check if field belongs to the grid views table
        if not view.table.field_set.filter(id=field.pk).exists():
            raise FieldNotInTable(
                f"The field {field.pk} does not belong to table {view.table.id}."
            )

        # Check if the field already exists as group
        if view.viewgroupby_set.filter(field_id=field.pk).exists():
            raise ViewGroupByFieldAlreadyExist(
                f"A group by for the field {field.pk} already exists."
            )

        view_group_by = ViewGroupBy.objects.create(
            pk=primary_key,
            view=view,
            field=field,
            order=order,
            width=width,
            type=sort_type,
        )

        view_group_by_created.send(self, view_group_by=view_group_by, user=user)

        return view_group_by

    def update_group_by(
        self,
        user: AbstractUser,
        view_group_by: ViewGroupBy,
        field: Optional[Field] = None,
        order: Optional[str] = None,
        width: Optional[int] = None,
        sort_type: Optional[str] = None,
    ) -> ViewGroupBy:
        """
        Updates the values of an existing view group_by.

        :param user: The user on whose behalf the view group by is updated.
        :param view_group_by: The view group by that needs to be updated.
        :param field: The field that must be grouped on.
        :param order: Indicates the group by order direction.
        :param width: The visual width of the group by.
        :param sort_type: The sort type that must be used, `default` is set as default
            when the sort is created.
        :raises ViewGroupByDoesNotExist: When the view used by the filter is trashed.
        :raises ViewGroupByFieldNotSupported: When the field does not support grouping.
        :raises FieldNotInTable:  When the provided field does not belong to the
            provided view's table.
        :return: The updated view group by instance.
        """

        if view_group_by.view.trashed:
            raise ViewGroupByDoesNotExist(
                f"The view {view_group_by.view.id} is trashed."
            )

        workspace = view_group_by.view.table.database.workspace
        field = field if field is not None else view_group_by.field
        order = order if order is not None else view_group_by.order
        width = width if width is not None else view_group_by.width
        sort_type = sort_type if sort_type is not None else view_group_by.type

        CoreHandler().check_permissions(
            user, ReadFieldOperationType.type, workspace=workspace, context=field
        )
        CoreHandler().check_permissions(
            user,
            UpdateViewGroupByOperationType.type,
            workspace=workspace,
            context=view_group_by,
        )

        # If the field has changed we need to check if the field belongs to the table.
        if (
            field.id != view_group_by.field_id
            and not view_group_by.view.table.field_set.filter(id=field.pk).exists()
        ):
            raise FieldNotInTable(
                f"The field {field.pk} does not belong to table "
                f"{view_group_by.view.table.id}."
            )

        # If the field has changed we need to check if the new field type supports
        # grouping.
        field_type = field_type_registry.get_by_model(field.specific_class)
        if (
            field.id != view_group_by.field_id or sort_type != view_group_by.type
        ) and not field_type.check_can_order_by(
            field,
            sort_type,
        ):
            raise ViewGroupByFieldNotSupported(
                f"The field {field.pk} does not support grouping."
            )

        # If the field has changed we need to check if the new field doesn't already
        # exist as group_by.
        if (
            field.id != view_group_by.field_id
            and view_group_by.view.viewgroupby_set.filter(field_id=field.pk).exists()
        ):
            raise ViewGroupByFieldAlreadyExist(
                f"A group by for the field {field.pk} already exists with type "
                f"{sort_type}."
            )

        view_group_by.field = field
        view_group_by.order = order
        view_group_by.width = width
        view_group_by.type = sort_type
        view_group_by.save()

        view_group_by_updated.send(self, view_group_by=view_group_by, user=user)

        return view_group_by

    def delete_group_by(self, user, view_group_by):
        """
        Deletes an existing view group_by.

        :param user: The user on whose behalf the view group by is deleted.
        :type user: User
        :param view_group_by: The view group by instance that needs to be deleted.
        :type view_group_by: ViewGroupBy
        """

        workspace = view_group_by.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            DeleteViewGroupByOperationType.type,
            workspace=workspace,
            context=view_group_by,
        )

        view_group_by_id = view_group_by.id
        view_group_by.delete()

        view_group_by_deleted.send(
            self,
            view_group_by_id=view_group_by_id,
            view_group_by=view_group_by,
            user=user,
        )

    def create_decoration(
        self,
        view: View,
        decorator_type_name: str,
        value_provider_type_name: str,
        value_provider_conf: Dict[str, Any],
        order: Optional[int] = None,
        user: Union["AbstractUser", None] = None,
        primary_key: Optional[int] = None,
    ) -> ViewDecoration:
        """
        Creates a new decoration based on the provided type.

        :param view: The view for which the filter needs to be created.
        :param decorator_type_name: The type of the decorator.
        :param value_provider_type_name: The value provider that provides the value
            to the decorator.
        :param value_provider_conf: The configuration used by the value provider to
            compute the values for the decorator.
        :param order: The order of the decoration.
        :param user: Optional user who is creating the decoration.
        :param primary_key: An optional primary key to give to the new view sort.
        :return: The created view decoration instance.
        """

        if user:
            workspace = view.table.database.workspace
            CoreHandler().check_permissions(
                user,
                CreateViewDecorationOperationType.type,
                workspace=workspace,
                context=view,
            )

        # Check if view supports decoration
        view_type = view_type_registry.get_by_model(view.specific_class)
        if not view_type.can_decorate:
            raise ViewDecorationNotSupported(
                f"Decoration is not supported for {view_type.type} views."
            )

        decorator_type = decorator_type_registry.get(decorator_type_name)
        decorator_type.before_create_decoration(view, user)

        if value_provider_type_name:
            value_provider_type = decorator_value_provider_type_registry.get(
                value_provider_type_name
            )
            value_provider_type.before_create_decoration(view, user)

            if not value_provider_type.decorator_is_compatible(decorator_type):
                raise DecoratorValueProviderTypeNotCompatible(
                    f"Value provider {value_provider_type_name} is not compatible with"
                    f"the decorator type {decorator_type_name}."
                )

        if order is None:
            order = ViewDecoration.get_last_order(view)

        view_decoration = ViewDecoration.objects.create(
            pk=primary_key,
            view=view,
            type=decorator_type_name,
            value_provider_type=value_provider_type_name,
            value_provider_conf=value_provider_conf,
            order=order,
        )

        view_decoration_created.send(self, view_decoration=view_decoration, user=user)

        return view_decoration

    def list_decorations(
        self, user: AbstractUser, view_id: int
    ) -> QuerySet[ViewDecoration]:
        """
        Lists view's decorations.

        :param user: The user on whose behalf are the decorations requested.
        :param view_id: The id of the view for which to list decorations.
        :return: ViewDecoration queryset for the particular view.
        """

        view = ViewHandler().get_view(view_id)
        CoreHandler().check_permissions(
            user,
            ListViewDecorationOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
        )
        decorations = ViewDecoration.objects.filter(view=view)
        return decorations

    def get_decoration(
        self,
        user: AbstractUser,
        view_decoration_id: int,
        base_queryset: QuerySet = None,
    ) -> ViewDecoration:
        """
        Returns an existing view decoration with the given id.

        :param user: The user on whose behalf is the decoration requested.
        :param view_decoration_id: The id of the view decoration.
        :param base_queryset: The base queryset from where to select the view decoration
            object from. This can for example be used to do a `select_related`.
        :raises ViewDecorationDoesNotExist: The requested view decoration does not
            exists.
        :return: The requested view decoration instance.
        """

        if base_queryset is None:
            base_queryset = ViewDecoration.objects

        try:
            view_decoration = base_queryset.select_related(
                "view__table__database__workspace"
            ).get(pk=view_decoration_id)
            workspace = view_decoration.view.table.database.workspace
            CoreHandler().check_permissions(
                user,
                ReadViewDecorationOperationType.type,
                workspace=workspace,
                context=view_decoration,
            )
        except ViewDecoration.DoesNotExist:
            raise ViewDecorationDoesNotExist(
                f"The view decoration with id {view_decoration_id} does not exist."
            )

        if TrashHandler.item_has_a_trashed_parent(
            view_decoration.view.table, check_item_also=True
        ):
            raise ViewDecorationDoesNotExist(
                f"The view decoration with id {view_decoration_id} does not exist."
            )

        return view_decoration

    def update_decoration(
        self,
        view_decoration: ViewDecoration,
        user: Union["AbstractUser", None] = None,
        decorator_type_name: Optional[str] = None,
        value_provider_type_name: Optional[str] = None,
        value_provider_conf: Optional[Dict[str, Any]] = None,
        order: Optional[int] = None,
    ) -> ViewDecoration:
        """
        Updates the values of an existing view decoration.

        :param view_decoration: The view decoration that needs to be updated.
        :param user: Optionally a user on whose behalf the decoration is updated.
        :param decorator_type_name: The type of the decorator.
        :param value_provider_type_name: The value provider that provides the value
            to the decorator.
        :param value_provider_conf: The configuration used by the value provider to
            compute the values for the decorator.
        :param order: The order of the decoration.
        :raises ViewDecorationDoesNotExist: The requested view decoration does not
            exists.
        :raises DecoratorValueProviderTypeNotCompatible: When the decorator value
            provided is not compatible with the decorator type.
        :return: The updated view decoration instance.
        """

        if user:
            workspace = view_decoration.view.table.database.workspace
            CoreHandler().check_permissions(
                user,
                UpdateViewDecorationOperationType.type,
                workspace=workspace,
                context=view_decoration,
            )

        if decorator_type_name is None:
            decorator_type_name = view_decoration.type
        if value_provider_type_name is None:
            value_provider_type_name = view_decoration.value_provider_type
        if value_provider_conf is None:
            value_provider_conf = view_decoration.value_provider_conf
        if order is None:
            order = view_decoration.order

        decorator_type = decorator_type_registry.get(decorator_type_name)
        decorator_type.before_update_decoration(view_decoration, user)

        if value_provider_type_name:
            value_provider_type = decorator_value_provider_type_registry.get(
                value_provider_type_name
            )
            value_provider_type.before_update_decoration(view_decoration, user)

            if not value_provider_type.decorator_is_compatible(decorator_type):
                raise DecoratorValueProviderTypeNotCompatible(
                    f"Value provider {value_provider_type_name} is not compatible with"
                    f"the decorator type {decorator_type_name}."
                )

        view_decoration.type = decorator_type_name
        view_decoration.value_provider_type = value_provider_type_name
        view_decoration.value_provider_conf = value_provider_conf
        view_decoration.order = order
        view_decoration.save()

        view_decoration_updated.send(self, view_decoration=view_decoration, user=user)

        return view_decoration

    def delete_decoration(
        self,
        view_decoration: ViewDecoration,
        user: Union["AbstractUser", None] = None,
    ):
        """
        Deletes an existing view decoration.

        :param view_decoration: The view decoration instance that needs to be deleted.
        :param user: Optional user who have deleted the decoration.
        :raises ViewDecorationDoesNotExist: The requested view decoration does not
            exists.
        """

        workspace = view_decoration.view.table.database.workspace
        CoreHandler().check_permissions(
            user,
            DeleteViewDecorationOperationType.type,
            workspace=workspace,
            context=view_decoration,
        )

        view_decoration_id = view_decoration.id
        view_decoration.delete()

        view_decoration_deleted.send(
            self,
            view_decoration_id=view_decoration_id,
            view_decoration=view_decoration,
            view_filter=view_decoration,
            user=user,
        )

    def get_queryset(
        self,
        user: Optional[AbstractUser],
        view: View,
        search: Optional[str] = None,
        model: Optional[GeneratedTableModel] = None,
        only_sort_by_field_ids: Optional[Iterable[int]] = None,
        only_search_by_field_ids: Optional[Iterable[int]] = None,
        apply_sorts: bool = True,
        apply_filters: bool = True,
        search_mode: Optional[SearchMode] = None,
    ) -> QuerySet:
        """
        Returns a queryset for the provided view which is appropriately sorted,
        filtered and searched according to the view type and its settings.

        :param user: The user on whose behalf the queryset is requested. This is needed
            for permission checks.
        :param search: A search term to apply to the resulting queryset.
        :param model: The model for this views table to generate the queryset from, if
            not specified then the model will be generated automatically.
        :param view: The view to get the export queryset and fields for.
        :param only_sort_by_field_ids: To only sort the queryset by some fields
            provide those field ids in this optional iterable. Other fields not
            present in the iterable will not have their view sorts applied even if they
            have one.
        :param only_search_by_field_ids: To only apply the search term to some
            fields provide those field ids in this optional iterable. Other fields
             not present in the iterable will not be searched and filtered down by the
             search term.
        :param apply_sorts: Whether to apply view sorts to the resulting queryset.
        :param apply_filters: Whether to apply view filters to the resulting queryset.
        :param search_mode: The type of search to perform if a search term is provided.
        :return: The appropriate queryset for the provided view.
        :raises ViewDoesNotSupportListingRows: When the view type does not support
            listing rows (i.e. a form view).
        """

        if model is None:
            model = view.table.get_model()

        queryset = model.objects.all().enhance_by_fields()

        view_type: ViewType = view_type_registry.get_by_model(view.specific_class)
        if not view_type.can_list_rows:
            raise ViewDoesNotSupportListingRows(
                f"The view type {view_type.type} does not support listing rows."
            )

        # Check if the view ownership type is enforcing the filters to be applied. If
        # so, then regardless of what argument is provided, the filters are applied to
        # the queryset. This can be useful if the view restricts access to rows that
        # don't match the filters.
        view_ownership_type = view_ownership_type_registry.get(view.ownership_type)
        if view_ownership_type.enforce_apply_filters(user, view):
            apply_filters = True

        if view_type.can_filter and apply_filters:
            queryset = self.apply_filters(view, queryset)
        if view_type.can_sort and apply_sorts:
            queryset = self.apply_sorting(
                view,
                queryset,
                only_sort_by_field_ids,
            )

        if search is not None:
            queryset = queryset.search_all_fields(
                search, only_search_by_field_ids, search_mode
            )
        return queryset

    def _get_aggregation_lock_cache_key(self, view: View):
        """
        Returns the aggregation lock cache key for the specified view.
        """

        return f"_aggregation__{view.pk}_lock"

    def _get_aggregation_value_cache_key(self, view: View, name: str):
        """
        Returns the aggregation value cache key for the specified view and name.
        """

        return f"aggregation_value__{view.pk}_{name}"

    def _get_aggregation_version_cache_key(self, view: View, name: str):
        """
        Returns the aggregation version cache key for the specified view and name.
        """

        return f"aggregation_version__{view.pk}_{name}"

    def clear_full_aggregation_cache(self, view: View):
        """
        Clears the cache key for the specified view.
        """

        view_type = view_type_registry.get_by_model(view.specific_class)
        aggregations = view_type.get_aggregations(view)
        cached_names = [agg[0].db_column for agg in aggregations]
        self.clear_aggregation_cache(view, cached_names)

    def clear_aggregation_cache(self, view: View, names: Union[List[str], str]):
        """
        Increments the version in cache for the specified view/name.
        """

        if not isinstance(names, list):
            names = [names]

        for name in names:
            cache_key = self._get_aggregation_version_cache_key(view, name)
            try:
                cache.incr(cache_key, 1)
            except ValueError:
                # No cache key, we create one
                cache.set(cache_key, 2)

    def _get_aggregations_to_compute(
        self,
        view: View,
        aggregations: Iterable[Tuple[django_models.Field, str]],
        no_cache: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, Tuple[django_models.Field, str, int]]]:
        """
        Figure out which aggregation needs to be computed and which one is cached.

        Returns a tuple with:
          - a dict of field_name -> cached values for values that are in the cache
          - a dict of values that need to be computed. keys are field name and values
            are a tuple with:
            - The field instance which aggregation needs to be computed
            - The aggregation_type
            - The current version
        """

        if not no_cache:
            names = [agg[0].db_column for agg in aggregations]
            # Get value and version cache all at once
            cached_keys = [
                self._get_aggregation_value_cache_key(view, name) for name in names
            ] + [self._get_aggregation_version_cache_key(view, name) for name in names]
            cached = cache.get_many(cached_keys)
        else:
            # We don't want to use cache for search query
            cached = {}

        valid_cached_values = {}
        need_computation = {}

        # Try to get field value from cache or add it to the need_computation list
        for field_instance, aggregation_type_name in aggregations:
            cached_value = cached.get(
                self._get_aggregation_value_cache_key(view, field_instance.db_column),
                {"version": 0},
            )
            cached_version = cached.get(
                self._get_aggregation_version_cache_key(view, field_instance.db_column),
                1,
            )

            # If the value version and the current version are the same we don't
            # need to recompute the value.
            if cached_value["version"] == cached_version:
                valid_cached_values[field_instance.db_column] = cached_value["value"]
            else:
                need_computation[field_instance.db_column] = {
                    "instance": field_instance,
                    "aggregation_type": aggregation_type_name,
                    "version": cached_version,
                }

        return (valid_cached_values, need_computation)

    def get_view_field_aggregations(
        self,
        user: AbstractUser,
        view: View,
        model: Union[GeneratedTableModel, None] = None,
        with_total: bool = False,
        adhoc_filters: Optional[AdHocFilters] = None,
        combine_filters: bool = False,
        search: Optional[str] = None,
        search_mode: Optional[SearchMode] = None,
        skip_perm_check: bool = False,
    ) -> Dict[str, Any]:
        """
        Returns a dict of aggregation for all aggregation configured for the view in
        parameters. Unless the search parameter is set to a non empty string,
        the aggregations values are cached when computed and must be
        invalidated when necessary.
        The dict keys are field names and value are aggregation values. The total is
        included in result if the with_total is specified.

        :param user: The user on whose behalf we are requesting the aggregations.
        :param view: The view to get the field aggregation for.aggregations
        :param model: The model for this view table to generate the aggregation
            query from, if not specified then the model will be generated
            automatically.
        :param with_total: Whether the total row count should be returned in the
            result.
        :param adhoc_filters: The filters that can be optionally applied.
        :param combine_filters: If set to True, the adhoc filters will be used
            together with the view filters. Otherwise ad hoc filters will be
            used if provided.
        :param search: the search string to considerate. If the search parameter is
            defined, we don't use the cache so we recompute aggregation on the fly.
        :param search_mode: the search mode that the search is using.
        :param skip_perm_check: If permission checks should be skipped,
            e.g. for public aggregations.
        :raises FieldAggregationNotSupported: When the view type doesn't support
            field aggregation.
        :return: A dict of aggregation value
        """

        if not skip_perm_check:
            CoreHandler().check_permissions(
                user,
                ListAggregationsViewOperationType.type,
                workspace=view.table.database.workspace,
                context=view,
                raise_permission_exceptions=True,
            )

        view_type = view_type_registry.get_by_model(view.specific_class)
        # Check if view supports field aggregation
        if not view_type.can_aggregate_field:
            raise FieldAggregationNotSupported(
                f"Field aggregation is not supported for {view_type.type} views."
            )

        # figure out which fields are visible
        visible_field_options = view_type.get_visible_field_options_in_order(view)
        visible_field_ids = {o.field_id for o in visible_field_options}

        if not adhoc_filters:
            adhoc_filters = AdHocFilters()

        adhoc_filters.only_filter_by_field_ids = visible_field_ids

        aggregations = view_type.get_aggregations(view)

        # filter out aggregations for hidden fields
        aggregations = [agg for agg in aggregations if agg[0].id in visible_field_ids]

        (
            values,
            need_computation,
        ) = self._get_aggregations_to_compute(
            view, aggregations, no_cache=search or adhoc_filters.has_any_filters
        )

        use_lock = hasattr(cache, "lock")
        used_lock = False
        if (
            not search
            and use_lock
            and (need_computation or with_total)
            and not adhoc_filters.has_any_filters
        ):
            # Lock the cache to avoid many updates when many queries arrive at same
            # times which happens when multiple users are on the same view.
            # This lock is optional. It avoid processing but doesn't break anything
            # if it fails so the timeout is low.
            cache_lock = cache.lock(
                self._get_aggregation_lock_cache_key(view), timeout=10
            )

            cache_lock.acquire()
            # We update the cache here because maybe it has changed in the meantime
            (values, need_computation) = self._get_aggregations_to_compute(
                view, aggregations, no_cache=search
            )
            used_lock = True

        # Do we need to compute some aggregations?
        if need_computation or with_total:
            db_result = self.get_field_aggregations(
                user,
                view,
                [
                    (n["instance"], n["aggregation_type"])
                    for n in need_computation.values()
                ],
                model,
                with_total=with_total,
                adhoc_filters=adhoc_filters,
                combine_filters=combine_filters,
                search=search,
                search_mode=search_mode,
                skip_perm_check=skip_perm_check,
                restrict_to_field_ids=visible_field_ids,
            )

            if not search and not adhoc_filters.has_any_filters:
                to_cache = {}
                for key, value in db_result.items():
                    # We don't cache total value
                    if key != "total":
                        to_cache[self._get_aggregation_value_cache_key(view, key)] = {
                            "value": value,
                            "version": need_computation[key]["version"],
                        }

                # Let's cache the newly computed values
                cache.set_many(to_cache)

            # Merged cached values and computed one
            values.update(db_result)

        if used_lock:
            try:
                cache_lock.release()
            except LockNotOwnedError:
                # If the lock release fails, it might be because of the timeout
                # and it's been stolen so we don't really care
                pass

        return values

    def get_field_aggregations(
        self,
        user: AbstractUser,
        view: View,
        aggregations: Iterable[Tuple[django_models.Field, str]],
        model: Union[GeneratedTableModel, None] = None,
        with_total: bool = False,
        adhoc_filters: Optional[AdHocFilters] = None,
        combine_filters: bool = False,
        search: Optional[str] = None,
        search_mode: Optional[SearchMode] = None,
        skip_perm_check: bool = False,
        restrict_to_field_ids: Optional[Set[int]] = None,
    ) -> Dict[str, Any]:
        """
        Returns a dict of aggregation for given (field, aggregation_type) couple list.
        The dict keys are field names and value are aggregation values. The total is
        included in result if the with_total is specified.

        :param user: The user on whose behalf we are requesting the aggregations.
        :param view: The view to get the field aggregation for.
        :param aggregations: A list of (field_instance, aggregation_type).
        :param model: The model for this view table to generate the aggregation
            query from, if not specified then the model will be generated
            automatically.
        :param with_total: Whether the total row count should be returned in the
            result.
        :param adhoc_filters: The filters that can be optionally applied.
        :param combine_filters: If set to True, the adhoc filters will be used
            together with the view filters. Otherwise ad hoc filters will be
            used if provided.
        :param search: the search string to consider.
        :param search: the mode that the search is in.
        :param skip_perm_check: Skips the permission check if not necessary.
        :param restrict_to_field_ids: Restrict the aggregations only to certain
            fields, for example if the aggregation is requested for public views.
        :raises FieldAggregationNotSupported: When the view type doesn't support
            field aggregation.
        :raises FieldNotInTable: When one of the field doesn't belong to the specified
            view.
        :return: A dict of aggregation values
        """

        if not skip_perm_check:
            CoreHandler().check_permissions(
                user,
                ReadAggregationsViewOperationType.type,
                workspace=view.table.database.workspace,
                context=view,
            )

        if model is None:
            model = view.table.get_model()

        if adhoc_filters is None:
            adhoc_filters = AdHocFilters()

        queryset = model.objects.all().enhance_by_fields()

        view_type = view_type_registry.get_by_model(view.specific_class)

        # Check if view supports field aggregation
        if not view_type.can_aggregate_field:
            raise FieldAggregationNotSupported(
                f"Field aggregation is not supported for {view_type.type} views."
            )

        # Apply filters and search to have accurate aggregations
        if view_type.can_filter:
            if combine_filters:
                queryset = self.apply_filters(view, queryset)
                queryset = adhoc_filters.apply_to_queryset(model, queryset)
            else:
                queryset = (
                    adhoc_filters.apply_to_queryset(model, queryset)
                    if adhoc_filters.has_any_filters
                    else self.apply_filters(view, queryset)
                )

        if search is not None:
            queryset = queryset.search_all_fields(
                search, restrict_to_field_ids, search_mode=search_mode
            )

        aggregation_dict = {}
        distribution_dict = {}

        for field_instance, aggregation_type_name in aggregations:
            field_name = field_instance.db_column

            # Check whether the field belongs to the table.
            if field_instance.table_id != view.table_id:
                raise FieldNotInTable(
                    f"The field {field_instance.pk} does not belong to table "
                    f"{view.table.id}."
                )

            field = model._field_objects[field_instance.id]["field"]
            model_field = model._meta.get_field(field_name)

            aggregation_type = view_aggregation_type_registry.get(aggregation_type_name)

            aggregation_object = aggregation_type.get_aggregation(
                field_name, model_field, field
            )

            if isinstance(aggregation_object, AnnotatedAggregation):
                # Check if the returned aggregations contain a `AnnotatedAggregation`,
                # and if so, apply the annotations and only keep the actual aggregation
                # in the dict. This is needed because some aggregations require
                # annotated values before they work.
                queryset = queryset.annotate(**aggregation_object.annotations)
                aggregation_dict[field_name] = aggregation_object.aggregation
            elif isinstance(aggregation_object, DistributionAggregation):
                # To calculate the results of every DistributionAggregation, we need
                # to pass in a copy of the current queryset, which may already have
                # filters and search applied to it. This is needed because a GROUP BY
                # is required for the distribution calculation, and applying a GROUP
                # BY on the original queryset will cause other aggregations to return
                # incorrect results.
                distribution_dict[field_name] = aggregation_object.calculate(
                    queryset.all()
                )
            else:
                # For any other aggregation type, we can simply execute it as is
                aggregation_dict[field_name] = aggregation_object

        # Add total to allow further calculation on the client if required
        if with_total:
            aggregation_dict["total"] = Count("id", distinct=True)

        aggregations = queryset.aggregate(**aggregation_dict)
        aggregations.update(distribution_dict)
        return aggregations

    def rotate_view_slug(
        self, user: AbstractUser, view: View, slug_field: str = "slug"
    ) -> View:
        """
        Rotates the slug of the provided view.

        :param user: The user on whose behalf the view is updated.
        :param view: The form view instance that needs to be updated.
        :return: The updated view instance.
        """

        new_slug = View.create_new_slug()
        return self.update_view_slug(user, view, new_slug, slug_field)

    def update_view_slug(
        self, user: AbstractUser, view: View, slug: str, slug_field: str = "slug"
    ) -> View:
        """
        Updates the slug of the provided view.

        :param user: The user on whose behalf the view is updated.
        :param view: The form view instance that needs to be updated.
        :param slug: The new slug to use to address this view.
        :return: The updated view instance.
        :raises CannotShareViewTypeError: Raised if called for a view which does not
            support sharing.
        """

        view_type = view_type_registry.get_by_model(view.specific_class)
        if not view_type.can_share:
            raise CannotShareViewTypeError()

        workspace = view.table.database.workspace
        CoreHandler().check_permissions(
            user, UpdateViewSlugOperationType.type, workspace=workspace, context=view
        )
        old_view = deepcopy(view)

        setattr(view, slug_field, slug)
        view.save()

        view_updated.send(self, view=view, user=user, old_view=old_view)

        return view

    def get_public_view_by_slug(
        self,
        user: Union[AbstractUser, AnonymousUser],
        slug: str,
        view_model: Optional[Type[View]] = None,
        authorization_token: Optional[str] = None,
        raise_authorization_error: bool = True,
    ) -> View:
        """
        Returns the view with the provided slug if it is public, if the user has
        access to the views workspace or provided a valid token in case the view is
        password protected.

        :param user: The user on whose behalf the view is requested.
        :param slug: The slug of the view.
        :param view_model: If provided that models objects are used to select the
            view. This can for example be useful when you want to select a GridView or
            other child of the View model.
        :param authorization_token: The token to use to access the view if the view is
            password protected and the user does not belong to the correct workspace.
        :param raise_authorization_error: Whether to raise an error if the user doesn't
            have access to the password protected shared view.
        :raises ViewDoesNotExist: Raised if the view does not exist, it has been
            trashed or the view is not public and the user doesn't belong to the
            workspace.
        :raises NoAuthorizationToPubliclySharedView: raised if the view is public but
            password protected and the user belongs to another workspace and doesn't
            provide a valid permission_token.
        :return: The requested view with matching slug.
        """

        if view_model is None:
            view_model = View

        try:
            view = view_model.objects.select_related("table__database__workspace").get(
                slug=slug
            )
        except (view_model.DoesNotExist, ValidationError) as exc:
            raise ViewDoesNotExist("The view does not exist.") from exc

        if TrashHandler.item_has_a_trashed_parent(view.table, check_item_also=True):
            raise ViewDoesNotExist("The view does not exist.")

        user_in_workspace = user and CoreHandler().check_permissions(
            user,
            ReadViewOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
            raise_permission_exceptions=False,
        )
        if not user_in_workspace:
            if not view.public:
                raise ViewDoesNotExist("The view does not exist.")

            token_is_valid_for_this_view = (
                authorization_token
                and self.is_public_view_token_valid(view, authorization_token)
            )
            if (
                view.public_view_has_password
                and not token_is_valid_for_this_view
                and raise_authorization_error
            ):
                raise NoAuthorizationToPubliclySharedView(
                    "The view is password protected."
                )

            view_ownership_type = view_ownership_type_registry.get(view.ownership_type)
            view_ownership_type.before_public_view_accessed(view)

        return view

    def submit_form_view(
        self,
        user,
        form,
        values,
        model: GeneratedTableModel | None = None,
        enabled_field_options=None,
    ):
        """
        Handles when a form is submitted. It will validate the data by checking if
        the required fields are provided and not empty and it will create a new row
        based on those values.

        :param form: The form view that is submitted.
        :type form: FormView
        :param values: The submitted values that need to be used when creating the row.
        :type values: dict
        :param model: If the model is already generated, it can be provided here.
        :type model: Model | None
        :param enabled_field_options: If the enabled field options have already been
            fetched, they can be provided here.
        :type enabled_field_options: QuerySet | list | None
        :return: The newly created row.
        :rtype: Model
        """

        table = form.table

        if model is None:
            model = table.get_model()

        if not enabled_field_options:
            enabled_field_options = form.active_field_options

        allowed_field_names = []
        field_errors = {}

        # Loop over all field options, find the name in the model and check if the
        # required values are provided. If not, a validation error is raised.
        for field in enabled_field_options:
            field_name = model._field_objects[field.field_id]["name"]
            allowed_field_names.append(field_name)

            if field.is_required() and (
                field_name not in values
                or value_is_empty_for_required_form_field(values[field_name])
            ):
                field_errors[field_name] = ["This field is required."]

        if len(field_errors) > 0:
            raise ValidationError(field_errors)

        allowed_values = extract_allowed(values, allowed_field_names)
        created_row = RowHandler().force_create_row(user, table, allowed_values, model)
        form_submitted.send(
            self, form=form, row=created_row, values=allowed_values, user=user
        )
        return created_row

    def restrict_row_for_view(
        self, view: View, serialized_row: Dict[str, Any]
    ) -> Dict[Any, Any]:
        """
        Removes any fields which are hidden in the view from the provided serialized
        row ensuring no data is leaked according to the views field options.

        :param view: The view to restrict the row by.
        :param serialized_row: A python dictionary which is the result of serializing
            the row containing `field_XXX` keys per field value. It must not be a
            serialized using user_field_names=True.
        :return: A copy of the serialized_row with all hidden fields removed.
        """

        return self.restrict_rows_for_view(view, [serialized_row])[0]

    def restrict_rows_for_view(
        self,
        view: View,
        serialized_rows: List[Dict[str, Any]],
        allowed_row_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Removes any fields which are hidden in the view and any rows that don't match
        the allowed list of ids from the provided serializes rows ensuring no data is
        leaked.

        :param view: The view to restrict the row by.
        :param serialized_rows: A list of python dictionaries which are the result of
            serializing the rows containing `field_XXX` keys per field value. They
            must not be serialized using user_field_names=True.
        :param allowed_row_ids: A list of ids of rows that can be returned. If set to
            None, all passed rows can be returned.
        :return: A copy of the allowed serialized_rows with all hidden fields removed.
        """

        view_type = view_type_registry.get_by_model(view.specific_class)
        hidden_field_ids = view_type.get_hidden_fields(view.specific)
        restricted_rows = []
        for serialized_row in serialized_rows:
            if allowed_row_ids is None or serialized_row["id"] in allowed_row_ids:
                row_copy = deepcopy(serialized_row)
                for hidden_field_id in hidden_field_ids:
                    row_copy.pop(f"field_{hidden_field_id}", None)
                restricted_rows.append(row_copy)
        return restricted_rows

    def _get_public_view_jwt_secret(self, view: View) -> str:
        """
        This method provides the secret to encode and decode the (non-expiring) JWT
        token used in password protected public views.
        By changing the `slug` or the `public_view_password`, previous tokens cannot
        be decoded anymore so the user will be forced to the password input page.
        Server's SECRET_KEY is used to be sure that the JWT cannot be guessed.
        :param view: The public view to restrict access to.
        :return: A string to use as secret to encode/decode JWT for the view.
        """

        return f"{view.slug}-{view.public_view_password}-{settings.SECRET_KEY}"

    def encode_public_view_token(self, view: View) -> str:
        """
        Create a non-expiring JWT token that authorize public requests for this view.
        :param view: The public view to restrict access to.
        :return: A string to use as JWT token to authorize the access for the view.
        """

        secret = self._get_public_view_jwt_secret(view)
        return jwt.encode(
            {"slug_id": view.slug},
            key=secret,
            algorithm=self.PUBLIC_VIEW_TOKEN_ALGORITHM,
        )

    def decode_public_view_token(self, view: View, token: str) -> Dict[str, Any]:
        """
        Decode the token using the view's secret.
        :param view: The public view to restrict access to.
        :param token: The JWT token to decode.
        :return: The payload decoded or, if invalid, a jwt.InvalidTokenError is raised.
        """

        secret = self._get_public_view_jwt_secret(view)
        return jwt.decode(
            token, key=secret, algorithms=[self.PUBLIC_VIEW_TOKEN_ALGORITHM]
        )

    def is_public_view_token_valid(self, view: View, token: str) -> bool:
        """
        Verify if the token provided is valid for the public view or not.
        :param view: The public view to restrict access to.
        :param token: The JWT token to decode.
        :return: True if the token is valid for the view, False otherwise.
        """

        try:
            self.decode_public_view_token(view, token)
            return True
        except jwt.InvalidTokenError:
            return False

    def get_public_rows_queryset_and_field_ids(
        self,
        view: View,
        search: str | None = None,
        search_mode: SearchMode | None = None,
        order_by: str | None = None,
        group_by: str | None = None,
        include_fields: str | None = None,
        exclude_fields: str | None = None,
        adhoc_filters: AdHocFilters | None = None,
        table_model: Type[GeneratedTableModel] | None = None,
        view_type: ViewType | None = None,
    ) -> Tuple[QuerySet, List[int], List[django_models.Model]]:
        """
        This function constructs a queryset which applies all the filters
        and restrictions required to only return rows that are supposed to
        be visible on a public view plus any additional filters given as
        parameters.

        It also returns the field_ids of the fields which are visible and
        the field_options.
        :param view: The public view to get rows for.
        :param search: A string to search for in the rows.
        :param search_mode: The type of search to perform.
        :param order_by: A string to order the rows by.
        :param group_by: A string group the rows by.
        :param include_fields: A comma separated list of field_ids to include.
        :param exclude_fields: A comma separated list of field_ids to exclude.
        :param adhoc_filters: Optional ad hoc filters to apply.
        :param table_model: A model which can be passed if it's already instantiated.
        :param view_type: The view_type which can be passed if it's already
            instantiated.
        :return: A tuple containing:
            - A queryset of rows.
            - A list of field_ids of the fields that are visible.
            - A list of field_options of the fields that are visible.
        :raises ViewDoesNotSupportListingRows: When the view type does not support
            listing rows (i.e. a form view).
        """

        if table_model is None:
            table_model = view.table.get_model()

        if view_type is None:
            view_type = view_type_registry.get_by_model(view)

        if not view_type.can_list_rows:
            raise ViewDoesNotSupportListingRows(
                f"The view type {view_type.type} does not support listing rows."
            )

        if adhoc_filters is None:
            adhoc_filters = AdHocFilters()

        visible_field_options = view_type.get_visible_field_options_in_order(view)
        visible_field_ids = {o.field_id for o in visible_field_options}

        field_ids = get_include_exclude_field_ids(
            view.table, include_fields, exclude_fields
        )

        # We have to still make a model with all fields as the public rows should still
        # be filtered by hidden fields.
        queryset = table_model.objects.all().enhance_by_fields()
        queryset = self.apply_filters(view, queryset)

        if view_type.can_group_by:
            has_group_by = group_by is not None and group_by != ""
            has_order_by = order_by is not None and order_by != ""
            # If both the group by and order by string is set, then we must merge the
            # two so that it will be sorted the right way because the grouping is
            # basically just sorting for the backend. However, the group by will take
            # precedence.
            if has_group_by and has_order_by:
                order_by = f"{group_by},{order_by}"
            # If only the group_by is set, then we can simply replace the order_by
            # because that must be applied to the queryset.
            elif has_group_by:
                order_by = group_by

        if order_by is not None and order_by != "":
            queryset = queryset.order_by_fields_string(
                order_by, False, visible_field_ids
            )

        if adhoc_filters.has_any_filters:
            adhoc_filters.only_filter_by_field_ids = visible_field_ids
            queryset = adhoc_filters.apply_to_queryset(table_model, queryset)

        if search:
            queryset = queryset.search_all_fields(
                search, visible_field_ids, search_mode=search_mode
            )

        field_ids = (
            list(set(field_ids) & set(visible_field_ids))
            if field_ids
            else visible_field_ids
        )

        return queryset, field_ids, visible_field_options

    def get_group_by_metadata_in_rows(
        self,
        fields: List[Field],
        rows: List["GeneratedTableModel"],
        base_queryset: QuerySet,
    ) -> Dict[Field, QuerySet]:
        """
        This method calculates the count of each unique value within the provided rows,
        grouped accordingly.

        :param fields: A list of the fields of the group bys in the right order.
        :param rows: The rows of the paginated query set. The unique values will be
            extracted from here.
        :param base_queryset: The base_queryset before the pagination was applied.
            This is needed because the rows that must be counted can be outside of
            the paginated range.
        :return: A dictionary where the key is the grouped by field, and the value a
            queryset containing the count per field.
        :raises ValueError: if a field is provided that cannot be grouped by.
        """

        qs_per_level = defaultdict(lambda: Q())
        unique_value_per_level = defaultdict(set)
        all_annotations = {}
        cte = {}

        for row in rows:
            all_values = tuple()
            all_filters = {}

            for level, field in enumerate(fields):
                field_name = field.db_column
                field_type = field_type_registry.get_by_model(field.specific_class)

                if not field_type.check_can_group_by(field, DEFAULT_SORT_TYPE_KEY):
                    raise ValueError(f"Can't group by {field_name}.")

                value = getattr(row, field_name)

                unique_value = field_type.get_group_by_field_unique_value(
                    field, field_name, value
                )
                all_values += (unique_value,)

                if all_values not in unique_value_per_level[level]:
                    (
                        filters,
                        annotations,
                    ) = field_type.get_group_by_field_filters_and_annotations(
                        field, field_name, base_queryset, unique_value, cte, rows
                    )

                    all_filters.update(**filters)
                    all_annotations.update(**annotations)
                    qs_per_level[level] |= Q(**all_filters)
                    unique_value_per_level[level].add(all_values)

        by_level = {}
        for level, q in qs_per_level.items():
            field_names = []

            for field in fields[: level + 1]:
                field_name = field.db_column
                field_names.append(field_name)

            # Wrap the queryset to avoid conflicts with annotations, orders, joins,
            # etc that can have an impact on the count.
            queryset = base_queryset.model.objects.filter(
                id__in=base_queryset.clear_multi_field_prefetch().values("id")
            ).values()

            if len(all_annotations) > 0:
                queryset = queryset.annotate(**all_annotations)

            queryset = (
                queryset.filter(q)
                .values(*field_names)
                .annotate(count=Count("id"))
                .order_by()
            )

            for cte_with in cte.values():
                queryset = queryset.with_cte(cte_with)

            by_level[fields[level]] = queryset

        return by_level

    def _get_prepared_values_for_data(
        self, view_type: ViewType, view: View, changed_allowed_keys: Iterable[str]
    ) -> Dict[str, Any]:
        return {
            key: value
            for key, value in view_type.export_prepared_values(view).items()
            if key in changed_allowed_keys
        }


class ViewSubscriptionHandler:
    @classmethod
    def get_subscribed_views(cls, subscriber: django_models.Model) -> QuerySet[View]:
        """
        Returns all views a subscriber is subscribed to.

        :param subscriber: The subscriber to get the views for.
        :return: A list of views the subscriber is subscribed to.
        """

        return View.objects.filter(
            id__in=ViewSubscription.objects.filter(
                subscriber_content_type=ContentType.objects.get_for_model(subscriber),
                subscriber_id=subscriber.pk,
            ).values("view_id")
        )

    @classmethod
    def sync_view_rows(cls, views: list[View], model=None) -> list[ViewRows]:
        """
        Updates or creates the ViewRows objects for the given views by executing
        the view queries and storing the resulting row IDs.

        :param views: The views for which to create ViewRows objects.
        :param model: The table model to use for the views. If not provided, the model
            will be generated automatically.
        :return: A list of created or updated ViewRows objects.
        """

        view_rows = []
        for view in views:
            row_ids = (
                ViewHandler()
                .get_queryset(None, view, model=model, apply_sorts=False)
                .values_list("id", flat=True)
            )
            view_rows.append(ViewRows(view=view, row_ids=list(row_ids)))

        return ViewRows.objects.bulk_create(
            view_rows,
            update_conflicts=True,
            update_fields=["row_ids"],
            unique_fields=["view_id"],
        )

    @classmethod
    def subscribe_to_views(cls, subscriber: django_models.Model, views: list[View]):
        """
        Subscribes a subscriber to the provided views. If the ViewRows already exist, it
        ensure to notify any changes to the subscriber first, so that the subscriber can
        be notified only for the changes that happened after the subscription.

        :param subscriber: The subscriber to subscribe to the views.
        :param views: The views to subscribe to.
        """

        cls.notify_table_views_updates(views)
        cls.sync_view_rows(views)

        new_subscriptions = []
        for view in views:
            new_subscriptions.append(ViewSubscription(subscriber=subscriber, view=view))
        ViewSubscription.objects.bulk_create(new_subscriptions, ignore_conflicts=True)

    @classmethod
    def unsubscribe_from_views(
        cls, subscriber: django_models.Model, views: list[View] | None = None
    ):
        """
        Unsubscribes a subscriber from the provided views. If the views are not
        provided, it unsubscribes the subscriber from all views. Make sure to use a
        table-specific model for the subscriber to avoid unsubscribing from views that
        are not related to the subscriber.

        :param subscriber: The subscriber to unsubscribe from the views.
        :param views: The views to unsubscribe from. If not provided, the subscriber
            will be unsubscribed
        """

        q = Q(
            subscriber_content_type=ContentType.objects.get_for_model(subscriber),
            subscriber_id=subscriber.pk,
        )
        if views is not None:
            q &= Q(view__in=views)

        ViewSubscription.objects.filter(q).delete()

    @classmethod
    def check_views_with_time_sensitive_filters(cls):
        """
        Checks for views that have time-sensitive filters. If a view has a
        time-sensitive filter, calling this method periodically ensure proper signals
        are emitted to notify subscribers that the view results have changed.
        """

        views = View.objects.filter(
            id__in=ViewFilter.objects.filter(
                type__in=view_filter_type_registry.get_time_sensitive_filter_types(),
                view__in=ViewSubscription.objects.values("view"),
            ).values("view_id")
        ).order_by("table", "id")
        for _, view_group in itertools.groupby(views, key=lambda f: f.table):
            view_ids = [v.id for v in view_group]
            if view_ids:
                cls.notify_table_views(view_ids)

    @classmethod
    def notify_table_views_updates(
        cls, views: list[View], model: GeneratedTableModel | None = None
    ):
        """
        Verify if the views have subscribers and notify them of any changes in the view
        results.

        :param views: The views to notify subscribers of.
        :param model: The table model to use for the views. If not provided, the model
            will be generated automatically.
        """

        view_ids_with_subscribers = ViewSubscription.objects.filter(
            view__in=views
        ).values_list("view_id", flat=True)
        if view_ids_with_subscribers:
            cls.notify_table_views(view_ids_with_subscribers, model)

    @classmethod
    def notify_table_views(
        cls, view_ids: list[int], model: GeneratedTableModel | None = None
    ):
        """
        Notify subscribers of any changes in the view results, emitting the appropriate
        signals and updating the ViewRows state.

        :param view_ids: The view ids to notify subscribers of.
        :param model: The table model to use for the views. If not provided, the model
            will be generated automatically
        """

        view_rows = list(
            ViewRows.objects.select_related("view__table")
            .filter(view_id__in=view_ids)
            .select_for_update(of=("self",))
            .order_by("view_id")
        )

        if model is None:
            model = view_rows[0].view.table.get_model()

        for view_state in view_rows:
            view = view_state.view
            new_row_ids, row_ids_entered, row_ids_exited = view_state.get_diff(model)
            changed = False
            if row_ids_entered:
                rows_entered_view.send(
                    sender=cls, view=view, row_ids=row_ids_entered, model=model
                )
                changed = True
            if row_ids_exited:
                rows_exited_view.send(
                    sender=cls, view=view, row_ids=row_ids_exited, model=model
                )
                changed = True
            if changed:
                view_state.row_ids = new_row_ids
                view_state.save()
