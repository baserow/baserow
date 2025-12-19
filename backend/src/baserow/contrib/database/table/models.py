import itertools
import re
import uuid
from collections import defaultdict
from types import MethodType
from typing import Iterable, Iterator, List, Optional, Type, TypedDict

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist as DjangoFieldDoesNotExist
from django.db import models
from django.db.models import BooleanField
from django.db.models import Field as DjangoModelFieldClass
from django.db.models import JSONField, Q, QuerySet

from django_cte.cte import CTEManager, CTEQuerySet
from opentelemetry import trace

from baserow.cachalot_patch import cachalot_enabled
from baserow.contrib.database.fields.exceptions import (
    FilterFieldNotFound,
    OrderByFieldNotFound,
    OrderByFieldNotPossible,
)
from baserow.contrib.database.fields.field_filters import (
    FILTER_TYPE_AND,
    FILTER_TYPE_OR,
    FilterBuilder,
    parse_ids_from_csv_string,
)
from baserow.contrib.database.fields.fields import IgnoreMissingForeignKey
from baserow.contrib.database.fields.models import (
    CreatedOnField,
    Field,
    LastModifiedField,
)
from baserow.contrib.database.fields.registries import FieldType, field_type_registry
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.contrib.database.search.handler import (
    ALL_SEARCH_MODES,
    SearchHandler,
    SearchMode,
)
from baserow.contrib.database.table.cache import (
    get_cached_model_field_attrs,
    set_cached_model_field_attrs,
)
from baserow.contrib.database.table.constants import (
    CREATED_BY_COLUMN_NAME,
    LAST_MODIFIED_BY_COLUMN_NAME,
    ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME,
    USER_TABLE_DATABASE_NAME_PREFIX,
)
from baserow.contrib.database.table.queryset import BaserowCTEQuerySet
from baserow.contrib.database.views.exceptions import ViewFilterTypeNotAllowedForField
from baserow.contrib.database.views.models import DEFAULT_SORT_TYPE_KEY
from baserow.contrib.database.views.registries import view_filter_type_registry
from baserow.core.cache import local_cache
from baserow.core.db import MultiFieldPrefetchQuerysetMixin, specific_iterator
from baserow.core.jobs.mixins import (
    JobWithUndoRedoIds,
    JobWithUserIpAddress,
    JobWithWebsocketId,
)
from baserow.core.jobs.models import Job
from baserow.core.mixins import (
    CreatedAndUpdatedOnMixin,
    HierarchicalModelMixin,
    OrderableMixin,
    TrashableModelMixin,
)
from baserow.core.telemetry.utils import baserow_trace
from baserow.core.utils import are_kwargs_default, split_comma_separated_string

extract_filter_sections_regex = re.compile(r"filter__(.+)__(.+)$")
field_id_regex = re.compile(r"field_(\d+)$")

tracer = trace.get_tracer(__name__)


User = get_user_model()


class FieldObject(TypedDict):
    type: FieldType
    field: Field
    name: str


class TableModelQuerySet(MultiFieldPrefetchQuerysetMixin, BaserowCTEQuerySet):
    def pg_search(
        self,
        input_search: str,
        only_search_by_field_ids: Optional[Iterable[int]] = None,
    ) -> QuerySet:
        """
        Responsible for narrowing the queryset down using Postgres full-text search.

        :param input_search: The search query to use for narrowing down the queryset. If
            empty, the queryset will not be narrowed down. If the sanitized search
            query is empty, an empty queryset will be returned.
        :param only_search_by_field_ids: If provided, only the fields with IDs in this
            iterable will be searched. If None, all searchable fields will be searched.
        :return: The narrowed queryset which contains the rows that match the provided
            search query for the searchable fields.
        """

        if not input_search or not input_search.strip():
            return self

        fields_to_search = [
            field
            for field in self.model.get_searchable_fields()
            if only_search_by_field_ids is None or field.id in only_search_by_field_ids
        ]
        return SearchHandler.full_text_search_in_table(
            self, input_search, fields_to_search
        )

    def count(self):
        with cachalot_enabled():
            return super().count()

    def enhance_by_fields(
        self, only_field_ids: Optional[List[int]] = None, **kwargs
    ) -> QuerySet:
        """
        Enhances the queryset based on the `enhance_queryset_in_bulk` for each unique
        field type used in the table. This one will eventually call the
        `enhance_queryset` for reach field in the table. For example the `link_row`
        field adds the `prefetch_related` to prevent N queries per row. This helper
        should only be used when multiple rows are going to be fetched.

        :param only_field_ids: only apply the prefetch related for the field with ID
          included in the given list.
        :return: The enhanced queryset.
        """

        selected_fields = (
            field
            for field in self.model._field_objects.values()
            if only_field_ids is None or field["field"].id in only_field_ids
        )

        by_type = defaultdict(list)
        for field_object in selected_fields:
            field_type = field_object["type"]
            by_type[field_type].append(field_object)
        for field_type, field_objects in by_type.items():
            self = field_type.enhance_queryset_in_bulk(self, field_objects, **kwargs)
        return self

    def search_all_fields(
        self,
        search: str,
        only_search_by_field_ids: Optional[Iterable[int]] = None,
        search_mode: Optional[SearchMode] = None,
    ):
        """
        Performs a very broad search across all supported fields with the given search
        query. If the primary key value matches then that result will be returned
        otherwise all field types other than link row and boolean fields are currently
        searched.

        :param search: The search query.
        :param only_search_by_field_ids: Only field ids in this iterable will be
            filtered by the search term. Other fields not in the iterable will be
            ignored and not be filtered.
        :param search_mode: In `COMPAT` we will use the old search method, using
            the LIKE operator on each column. In `FT_WITH_COUNT`  we will switch
            to using Postgres full-text search.
        :return: The queryset containing the search queries.
        :rtype: QuerySet
        """

        search_mode = search_mode or settings.DEFAULT_SEARCH_MODE
        if search_mode not in ALL_SEARCH_MODES:
            raise NotImplementedError(f"Unsupported search_mode {search_mode}.")

        can_use_full_text_search = SearchHandler.can_use_full_text_search(
            self.model.baserow_table
        )

        if search_mode == SearchMode.FT_WITH_COUNT and can_use_full_text_search:
            return self.pg_search(search, only_search_by_field_ids)
        else:
            return self.compat_search(search, only_search_by_field_ids)

    def compat_search(self, search: str, only_search_by_field_ids=None):
        """
        Responsible for executing our original search behaviour, using the
        LIKE operator on each field in the table.
        """

        filter_builder = FilterBuilder(filter_type=FILTER_TYPE_OR)

        SearchHandler.add_exact_id_search(filter_builder, search)
        for field_object in self.model._field_objects.values():
            if (
                only_search_by_field_ids is not None
                and field_object["field"].id not in only_search_by_field_ids
            ):
                continue
            field_name = field_object["name"]
            model_field = self.model._meta.get_field(field_name)

            try:
                sub_filter = field_object["type"].contains_query(
                    field_name, search, model_field, field_object["field"]
                )
                filter_builder.filter(sub_filter)
            except Exception:  # nosec B112
                continue

        return filter_builder.apply_to_queryset(self)

    def _get_field_name(self, field: str) -> str:
        """
        Helper method for parsing a field name from a string
        with a possible prefix.

        :param field: The string from which the field name
            should be parsed.
        :type field: str
        :return: The field without prefix.
        :rtype: str
        """

        possible_prefix = field[:1]
        if possible_prefix in {"-", "+"}:
            return field[1:]
        else:
            return field

    def order_by_fields_string(
        self, order_string, user_field_names=False, only_order_by_field_ids=None
    ):
        """
        Orders the query by the given field order string. This string is often
        directly forwarded from a GET, POST or other user provided parameter.
        Multiple fields can be provided by separating the values by a comma. When
        user_field_names is False the order_string must contain a comma separated
        list of field ids. The field id is extracted from the string so it can either
        be provided as field_1, 1, id_1, etc. When user_field_names is True the
        order_string is treated as a comma separated list of the actual field names,
        use quotes to wrap field names containing commas.

        :param order_string: The field ids to order the queryset by separated by a
            comma. For example `field_1,2` which will order by field with id 1 first
            and then by field with id 2 second.
        :type order_string: str
        :param user_field_names: If true then the order_string is instead treated as
        a comma separated list of actual field names and not field ids.
        :type user_field_names: bool
        :param only_order_by_field_ids: Only field ids in this iterable will be
            ordered by. Other fields not in the iterable will be ignored and not be
            filtered.
        :type only_order_by_field_ids: Optional[Iterable[int]]
        :raises OrderByFieldNotFound: when the provided field id is not found in the
            model.
        :raises OrderByFieldNotPossible: when it is not possible to order by the
            field's type.
        :return: The queryset ordered by the provided order_string.
        :rtype: QuerySet
        """

        order_by_fields = split_comma_separated_string(order_string)

        if user_field_names:
            field_object_dict = {
                o["field"].name: o for o in self.model._field_objects.values()
            }
        else:
            field_object_dict = self.model._field_objects

        annotations = {}
        order_by = []
        for order in order_by_fields:
            if user_field_names:
                field_name_or_id = self._get_field_name(order)
            else:
                field_name_or_id = get_field_id_from_field_key(order, False)

            if field_name_or_id not in field_object_dict or (
                only_order_by_field_ids is not None
                and field_name_or_id not in only_order_by_field_ids
            ):
                raise OrderByFieldNotFound(order)

            order_direction = "DESC" if order[:1] == "-" else "ASC"
            type_match = re.search(r"\[(.*?)\]", order)
            sort_type = type_match.group(1) if type_match else DEFAULT_SORT_TYPE_KEY
            field_object = field_object_dict[field_name_or_id]
            field_type = field_object["type"]
            field_name = field_object["name"]
            field = field_object["field"]
            user_field_name = field_object["field"].name
            error_display_name = user_field_name if user_field_names else field_name

            if not field_object["type"].check_can_order_by(
                field_object["field"], sort_type
            ):
                raise OrderByFieldNotPossible(
                    error_display_name,
                    field_type.type,
                    sort_type,
                    f"It is not possible to order by field type {field_type.type} using sort type {sort_type}.",
                )

            field_annotated_order_by = field_type.get_order(
                field, field_name, order_direction, sort_type, table_model=self.model
            )

            if field_annotated_order_by.annotation is not None:
                annotations = {**annotations, **field_annotated_order_by.annotation}
            field_order_bys = field_annotated_order_by.order_bys
            for field_order_by in field_order_bys:
                order_by.append(field_order_by)

        order_by.append("order")
        order_by.append("id")

        return self.annotate(**annotations).order_by(*order_by)

    def filter_by_fields_object(
        self,
        filter_object,
        filter_type=FILTER_TYPE_AND,
        only_filter_by_field_ids=None,
        user_field_names=False,
    ):
        """
        Filters the query by the provided filters in the filter_object. The following
        format `filter__field_{id}__{view_filter_type}` is expected as key and multiple
        values can be provided as a list containing strings. Only the view filter types
        are allowed.

        Example: {
            'filter__field_{id}__{view_filter_type}': {value}.
        }

        In addition to that, it's also possible to directly filter on the
        `created_on` and `updated_on` fields, even if the CreatedOn and LastModified
        fields are not created. This can be done by providing
        `filter__field_created_on__{view_filter_type}` or
        `filter__field_updated_on__{view_filter_type}` as keys in the `filter_object`.

        :param filter_object: The object containing the field and filter type as key
            and the filter value as value.
        :type filter_object: object
        :param filter_type: Indicates if the provided filters are in an AND or OR
            statement.
        :type filter_type: str
        :param only_filter_by_field_ids: Only field ids in this iterable will be
            filtered by. Other fields not in the iterable will be ignored and not be
            filtered.
        :type only_filter_by_field_ids: Optional[Iterable[int]]
        :param user_field_names: If True, use field names in the filter object
            instead of ids
        :type user_field_names: bool
        :raises ValueError: Raised when the provided filer_type isn't AND or OR.
        :raises FilterFieldNotFound: Raised when the provided field isn't found in
            the model.
        :raises ViewFilterTypeDoesNotExist: when the view filter type doesn't exist.
        :raises ViewFilterTypeNotAllowedForField: when the view filter type isn't
            compatible with field type.
        :return: The filtered queryset.
        :rtype: QuerySet
        """

        if filter_type not in [FILTER_TYPE_AND, FILTER_TYPE_OR]:
            raise ValueError(f"Unknown filter type {filter_type}.")

        filter_builder = FilterBuilder(filter_type=filter_type)

        user_field_name_to_id_mapping = (
            {v["field"].name: k for k, v in self.model._field_objects.items()}
            if user_field_names
            else {}
        )

        fixed_field_instance_mapping = {
            "field_created_on": CreatedOnField(),
            "field_updated_on": LastModifiedField(),
            "field_id": None,
        }

        for key, values in filter_object.items():
            filter_sections = extract_filter_sections_regex.match(key)
            if not filter_sections:
                continue

            field_name_or_id, view_filter_name = filter_sections.groups()

            if field_name_or_id == "field_id" and view_filter_name == "in":
                if not values:
                    continue
                row_ids = parse_ids_from_csv_string(values[0])
                if row_ids:
                    filter_builder.filter(Q(id__in=row_ids))
                continue

            if user_field_names and field_name_or_id in user_field_name_to_id_mapping:
                field_id = user_field_name_to_id_mapping[field_name_or_id]
            elif field_name_or_id in fixed_field_instance_mapping.keys():
                field_instance = fixed_field_instance_mapping[field_name_or_id]
                field_name = field_name_or_id.replace("field_", "")
            else:
                field_id_match = field_id_regex.match(field_name_or_id)
                if field_id_match:
                    field_id = int(field_id_match.group(1))
                else:
                    continue

            if field_name_or_id not in fixed_field_instance_mapping.keys():
                if field_id not in self.model._field_objects or (
                    only_filter_by_field_ids is not None
                    and field_id not in only_filter_by_field_ids
                ):
                    raise FilterFieldNotFound(
                        field_id, f"Field {field_id} does not exist."
                    )

                field_object = self.model._field_objects[field_id]
                field_instance = field_object["field"]
                field_name = field_object["name"]
                field_type = field_object["type"].type

            model_field = self.model._meta.get_field(field_name)
            view_filter_type = view_filter_type_registry.get(view_filter_name)

            if not view_filter_type.field_is_compatible(field_instance):
                raise ViewFilterTypeNotAllowedForField(
                    view_filter_name,
                    field_type,
                )

            if not isinstance(values, list):
                values = [values]

            for value in values:
                filter_builder.filter(
                    view_filter_type.get_filter(
                        field_name, value, model_field, field_instance
                    )
                )

        return filter_builder.apply_to_queryset(self)


class TableModelTrashAndObjectsManager(models.Manager):
    @classmethod
    def from_queryset(cls, queryset_class, class_name=None):
        if not issubclass(queryset_class, CTEQuerySet):
            raise TypeError("models with CTE support need to use a CTEQuerySet")
        return super(CTEManager, cls).from_queryset(
            queryset_class, class_name=class_name
        )

    def get_queryset(self):
        qs = TableModelQuerySet(self.model, using=self._db)
        return qs


class TableModelManager(TableModelTrashAndObjectsManager):
    def get_queryset(self):
        return super().get_queryset().filter(trashed=False)


class GeneratedTableModel(HierarchicalModelMixin, models.Model):
    """
    Mixed into Model classes which have been generated by Baserow.
    Can also be used to identify instances of generated baserow models
    like `isinstance(possible_baserow_model, GeneratedTableModel)`.
    """

    @classmethod
    def info(cls):
        """
        Print basic information about the generated table.

        Use only in development.
        """

        from rich import box
        from rich.console import Console
        from rich.table import Table

        table = Table(
            title=f"{cls.baserow_table.name} ({cls.baserow_table.id})", box=box.ROUNDED
        )
        table.add_column("Name", justify="right", style="cyan", no_wrap=True)
        table.add_column("Column", justify="right", style="cyan", no_wrap=True)
        table.add_column("Type", style="magenta")
        table.add_column("Order", style="grey84")
        table.add_column("Trashed", justify="center", style="green")
        table.add_column("TS vector column", style="yellow")

        field_objects = cls.get_field_objects(include_trash=True)
        for field_obj in field_objects:
            primary = "(primary) " if field_obj["field"].primary else ""
            name = f"{primary}{field_obj['field'].name}"
            trashed = "🗑️" if field_obj["field"].trashed else ""
            table.add_row(
                name,
                field_obj["field"].db_column,
                field_obj["type"].type,
                str(field_obj["field"].order),
                trashed,
            )

        console = Console()
        console.print(table)

    @classmethod
    def get_parent(cls):
        return cls.baserow_table

    @classmethod
    def get_root(cls):
        return cls.baserow_table.get_root()

    @classmethod
    def fields_requiring_refresh_after_insert(cls):
        return [
            f.attname
            for f in cls._meta.fields
            if getattr(f, "requires_refresh_after_insert", False)
            # There is a bug in Django where db_returning fields do not have their
            # from_db_value function applied after performing and INSERT .. RETURNING
            # Instead for now we force a refresh to ensure these fields are converted
            # from their db representations correctly.
            or isinstance(f, JSONField) and f.db_returning
        ]

    @classmethod
    def fields_requiring_refresh_after_update(cls):
        return [
            f.attname
            for f in cls._meta.fields
            if getattr(f, "requires_refresh_after_update", False)
        ]

    @classmethod
    def get_field_object(
        cls, field_name: str, include_trash: bool = False
    ) -> FieldObject:
        field_objects = cls.get_field_objects(include_trash)

        try:
            return next(filter(lambda f: f["name"] == field_name, field_objects))
        except StopIteration:
            raise ValueError(f"Field {field_name} not found.")

    @classmethod
    def get_field_object_by_id(
        cls, field_id: int, include_trash: bool = False
    ) -> FieldObject:
        field_objects = cls.get_field_objects(include_trash)

        try:
            return next(filter(lambda f: f["field"].id == field_id, field_objects))
        except StopIteration:
            raise ValueError(f"Field with ID {field_id} not found.")

    @classmethod
    def get_field_object_by_user_field_name(
        cls, field_name: str, include_trash: bool = False
    ) -> FieldObject:
        field_objects = cls.get_field_objects(include_trash)

        try:
            return next(filter(lambda f: f["field"].name == field_name, field_objects))
        except StopIteration:
            raise ValueError(f"Field {field_name} not found.")

    @classmethod
    def get_field_objects(cls, include_trash: bool = False) -> List[FieldObject]:
        field_objects = cls._field_objects.values()
        if include_trash:
            field_objects = itertools.chain(
                field_objects, cls._trashed_field_objects.values()
            )
        return field_objects

    @classmethod
    def get_field_objects_to_always_update(cls) -> List[FieldObject]:
        field_objects = cls.get_field_objects(True)
        return [
            field_object
            for field_object in field_objects
            if field_type_registry.get_by_type(field_object["type"]).update_always
            is True
        ]

    @classmethod
    def get_fields_with_uninitialized_search_data(
        cls, include_trash: bool = False
    ) -> List[Field]:
        """
        Returns a list of fields which have not yet had their search data
        initialized. This is useful for identifying fields that need to be
        processed for search indexing.

        :param include_trash: Whether to include trashed fields in the result
        :return: A list of Field objects that need to be initialized for search.
        """

        return (
            f
            for f in cls.get_searchable_fields(include_trash)
            if f.search_data_initialized_at is None
        )

    @classmethod
    def get_searchable_fields(cls, include_trash: bool = False) -> Iterator[Field]:
        """
        Generates all searchable fields in a table. A searchable field is one where
        field_type.is_searchable(field) is true.

        :param include_trash: Whether to include trashed searchable fields in the result
        :return: A generator of Field.
        """

        for field_object in cls.get_field_objects(include_trash):
            field_type = field_object["type"]
            field = field_object["field"]

            if field_type.is_searchable(field):
                yield field

    @classmethod
    def get_fields(cls, include_trash=False) -> List[Field]:
        return [o["field"] for o in cls.get_field_objects(include_trash)]

    @classmethod
    def get_primary_field(self) -> Field:
        field_objects = self.get_field_objects()

        try:
            field_object = next(
                filter(lambda f: f["field"].primary is True, field_objects)
            )
            return field_object["field"]
        except StopIteration:
            return None

    class Meta:
        abstract = True

    def get_primary_field_value(self):
        primary_field = self.get_primary_field()
        if primary_field is None:
            return
        return getattr(self, primary_field.db_column, None)


class GeneratedModelAppsProxy:
    """
    A proxy class to the default apps registry. This class is needed to make our dynamic
    models available in the options when the relation tree is built, without polluting
    the global apps registry, meant to keep only the static models that do not change.

    This permits to Django to find the reverse relation in the _relation_tree. Look into
    django.db.models.options.py - _populate_directed_relation_graph for more
    information.

    It also allows us to register dynamic models in a separate registry and to perform
    all the pending operations for the generated models without the need of clearing the
    global apps registry cache.

    This registry, created as needed by a generated table model, holds references to
    other such models. It's discarded after the operation, ensuring it only exists when
    necessary.
    """

    def __init__(self, baserow_models=None, app_label=None):
        self.baserow_models = baserow_models or {}
        self.baserow_app_label = app_label or "database_table"

    def get_models(self, *args, **kwargs):
        """
        Called by django and must contain ALL the models that have been generated
        and connected together as django will loop over every model in this list
        and set cached properties on each. These cached django properties are then
        used to when looking up fields, so they must include every connected model
        that could be involved in queries and not just a sub-set of them.
        """

        return apps.get_models(*args, **kwargs) + list(self.baserow_models.values())

    def register_model(self, app_label, model):
        """
        This is hack that prevents a generated table model and related auto created
        models from being registered into the Django apps model registry. It tries to
        keep separate Django's model registry from Baserow's generated models. In this
        way we can leverage all the great features of Django's static models, while
        still being able to generate dynamic models for tables, without polluting the
        global ones.
        """

        # Use the RLock defined in the apps registry to prevent any thead from
        # accessing the apps registry concurrently because it's not thread safe.
        with self._lock:
            model_name = model._meta.model_name.lower()
            if not hasattr(model, "_generated_table_model"):
                # it must be an auto created intermediary m2m model, so use a list of
                # baserow models we can later use to resolve the pending operations.
                if not hasattr(self, "baserow_models"):
                    self.baserow_models = model._meta.auto_created.baserow_models

            self.baserow_models[model_name] = model
            self.do_all_pending_operations()
            self._clear_baserow_models_cache()

            # The `all_models` is a defaultdict, and will therefore have a residual
            # empty key in with the app label because the app label is uniquely
            # generated. This will make sure it's cleared.
            try:
                del apps.all_models[self.baserow_app_label]
            except KeyError:
                pass

    def _clear_baserow_models_cache(self):
        for model in self.baserow_models.values():
            model._meta._expire_cache()

    def do_all_pending_operations(self):
        """
        This method will perform all the pending operations for the generated models.
        It will keep performing the pending operations until there are no more pending
        operations left. It will perform a maximum of `max_iterations` to prevent
        infinite loops and because one pending operation can trigger another pending
        operation for another model. The number of 3 has been chosen because it's
        the number observed to be enough to resolve all pending operations in the
        tests.
        """

        max_iterations = 3
        for _ in range(max_iterations):
            # Only do pending operations of models with the same app label because
            # if we don't do that, and the same model is generated at the same time
            # there can be conflicts because the `model_name` will be the same. The
            # `app_label` is uniquely generated to avoid `model_name` conflicts.
            pending_operations_for_app_label = [
                (app_label, model_name)
                for app_label, model_name in list(apps._pending_operations.keys())
                if app_label == self.baserow_app_label
            ]
            for _, model_name in list(pending_operations_for_app_label):
                model = self.baserow_models[model_name]
                apps.do_pending_operations(model)

            if not pending_operations_for_app_label:
                break

    def __getattr__(self, attr):
        return getattr(apps, attr)


def patch_meta_get_field(_meta):
    original_get_field = _meta.get_field

    def get_field(self, field_name, *args, **kwargs):
        try:
            return original_get_field(field_name, *args, **kwargs)
        except DjangoFieldDoesNotExist as exc:
            try:
                field_object = self.model.get_field_object(
                    field_name, include_trash=True
                )

            except ValueError:
                raise exc

            field_type = field_object["type"]
            field_type.after_model_generation(
                field_object["field"], self.model, field_object["name"]
            )
            return original_get_field(field_name, *args, **kwargs)

    _meta.get_field = MethodType(get_field, _meta)


class TableUsageUpdate(models.Model):
    """
    This table maintains an entry for each table where the 'row_count' or
    'storage_usage' has changed due to an operation on the table (e.g., a new row
    insertion or a new file in a file field).

    Given the following considerations:
        - to allow concurrent requests to insert/update/delete rows on the same tables,
          we cannot update the TableUsage entry or any other shared resource
          synchronously.
        - even if we perform the update asynchronously in a celery task, the
          operations to recount rows and calculate storage usage might be slow.
          We want to avoid running these operations every time a change occurs.

    We use this table to insert/update the corresponding table entry with a relative
    'row_count' (if available) in an asynchronous celery task. This approach allows
    concurrent operations to run simultaneously. The row count displayed in the admin
    panel can be more accurate by using this value as a delta.

    However, 'storage_usage' needs to be recalculated every time there is an entry in
    this table. This is because it's challenging to determine if a change related to a
    file field references a newly uploaded file or not.
    """

    id = models.BigAutoField(
        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
    )
    table = models.ForeignKey(
        "database.Table", on_delete=models.CASCADE, related_name="usage_update"
    )
    row_count = models.IntegerField(
        null=True,
        help_text="The change in the row count value. It can be positive or negative."
        "A null value means that the row_count is not changed, but it might be changed "
        "storage count and we want to recalculate the storage needed by this table.",
    )
    timestamp = models.DateTimeField(auto_now=True)


class TableUsage(models.Model):
    """
    This table stores the resources required by the associated table. It gets updated
    whenever the `UsageHandler.calculate_storage_usage_workspace()` method is executed.
    This method runs for all tables that either have an entry in the `TableUsageUpdate`
    table or do not have an entry yet.
    """

    table = models.OneToOneField(
        "database.Table", on_delete=models.CASCADE, related_name="usage"
    )
    row_count = models.PositiveIntegerField(
        null=True, help_text="The number of non-trashed rows of the linked table."
    )
    row_count_updated_at = models.DateTimeField(null=True)
    storage_usage = models.PositiveIntegerField(
        null=True,
        help_text="The storage needed in MB by files saved in file fields of the linked table.",
    )
    storage_usage_updated_at = models.DateTimeField(null=True)


class Table(
    HierarchicalModelMixin,
    TrashableModelMixin,
    CreatedAndUpdatedOnMixin,
    OrderableMixin,
    models.Model,
):
    database = models.ForeignKey("database.Database", on_delete=models.CASCADE)
    order = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    _row_count = models.PositiveIntegerField(
        null=True,
        db_column="row_count",
        help_text="Deprecated: use usage.row_count instead. "
        "This field will be removed in a future version.",
    )
    _row_count_updated_at = models.DateTimeField(
        null=True,
        db_column="row_count_updated_at",
        help_text="Deprecated: use usage.row_count_updated_at instead. "
        "This field will be removed in a future version.",
    )
    version = models.TextField(default="initial_version")
    needs_background_update_column_added = models.BooleanField(
        default=False,
        help_text="Indicates whether the table has had the background_update_needed "
        "column added. (DEPRECATED: remove in a future version)",
    )
    last_modified_by_column_added = models.BooleanField(
        default=True,
        null=True,
        help_text="Indicates whether the table has had the last_modified_by "
        "column added.",
    )
    created_by_column_added = models.BooleanField(
        default=True,
        null=True,
        help_text="Indicates whether the table has had the created_by column added.",
    )
    field_rules_validity_column_added = models.BooleanField(
        db_default=False,
        default=False,
        null=True,
        help_text="Indicates whether the table has had the field_rules_are_valid column added.",
    )
    # The m2m indexes of the foreign keys were not added before because the
    # `schema_editor.add_field` does not add them. The `schema_editor.create_model`
    # does add those. This problem has been addressed, but there are tables out there
    # without those indexes.
    missing_m2m_indexes_added = models.BooleanField(
        # The `db_default` must be false because this is used when an entry is created
        # no default value is set. This is what happens when the field index changes
        # are not yet deployed, so index does not exist.
        db_default=False,
        # However, if the field index changes are deployed, this default value is used,
        # and in that case, the index has been applied.
        default=True,
        help_text="Indicates whether potentially missing m2m foreign key indexes have been added.",
    )

    class Meta:
        ordering = ("order",)

    @property
    def is_data_synced_table(self) -> bool:
        return hasattr(self, "data_sync") and self.data_sync is not None

    @property
    def is_read_only_data_synced_table(self) -> bool:
        return self.is_data_synced_table and not self.data_sync.two_way_sync

    @property
    def is_two_way_data_synced_table(self) -> bool:
        return self.is_data_synced_table and self.data_sync.two_way_sync

    def get_parent(self):
        return self.database

    def get_primary_field(self) -> Field:
        return self.field_set.filter(primary=True).first()

    @classmethod
    def get_last_order(cls, database):
        queryset = Table.objects.filter(database=database)
        return cls.get_highest_order_of_queryset(queryset) + 1

    @classmethod
    def get_table_model_name(cls, table_id):
        return f"Table{table_id}Model"

    def get_database_table_name(self):
        return f"{USER_TABLE_DATABASE_NAME_PREFIX}{self.id}"

    @baserow_trace(tracer)
    def get_model(self, **kwargs):
        """
        Get model from local cache if the kwargs are the default values.
        See `_get_model` doc for more information.
        """

        if are_kwargs_default(self._get_model, **kwargs):
            return local_cache.get(
                f"database_table_model_{self.id}", lambda: self._get_model(**kwargs)
            )
        return self._get_model(**kwargs)

    def _get_model(
        self,
        fields=None,
        field_ids=None,
        field_names=None,
        attribute_names=False,
        manytomany_models=None,
        add_dependencies=True,
        managed=False,
        use_cache=True,
        app_label: Optional[str] = None,
    ) -> Type[GeneratedTableModel]:
        """
        Generates a temporary Django model based on available fields that belong to
        this table.

        :param fields: Extra table field instances that need to be added the model.
        :type fields: list
        :param field_ids: If provided only the fields with the ids in the list will be
            added to the model. This can be done to improve speed if for example only a
            single field needs to be mutated.
        :type field_ids: None or list
        :param field_names: If provided only the fields with the names in the list
            will be added to the model. This can be done to improve speed if for
            example only a single field needs to be mutated.
        :type field_names: None or list
        :param attribute_names: If True, the model attributes will be based on the
            field name instead of the field id.
        :type attribute_names: bool
        :param manytomany_models: In some cases with related fields a model has to be
            generated in order to generate that model. In order to prevent a
            recursion loop we cache the generated models and pass those along.
        :type manytomany_models: dict
        :param add_dependencies: When True will ensure any direct field dependencies
            are included in the model. Otherwise, only the exact fields you specify
            will be added to the model.
        :param managed: Whether the created model should be managed by Django or not.
            Only in very specific limited situations should this be enabled as
            generally Baserow itself manages most aspects of returned generated models.
        :type managed: bool
        :param use_cache: Indicates whether a cached model can be used.
        :type use_cache: bool
        :param app_label: In some cases with related fields, the related models must
            have the same app_label. If passed along in this parameter, then the
            generated model will use that one instead of generating a unique one.
        :type app_label: Optional[String]
        :return: The generated model.
        :rtype: Model
        """

        if app_label is None:
            # Generate a unique app_label to make the generation of the model thread
            # safe. Related fields generate pending operations in the `apps`
            # registry, but they're identified by the model class name. If the same
            # model is generated at the same time, the pending operations can be
            # executed in a wrong order. A unique app_label isolated in that case.
            app_label = str(uuid.uuid4()) + "_database_table"

        filtered = field_names is not None or field_ids is not None
        model_name = self.get_table_model_name(self.pk)

        if fields is None:
            fields = []

        # By default, we create an index on the `order` and `id`
        # columns.
        indexes = [
            models.Index(
                fields=["order", "id"],
                name=self.get_collision_safe_order_id_idx_name(),
            )
        ]

        apps = GeneratedModelAppsProxy(manytomany_models, app_label)
        meta = type(
            "Meta",
            (),
            {
                "apps": apps,
                "managed": managed,
                "db_table": self.get_database_table_name(),
                "app_label": app_label,
                "ordering": ["order", "id"],
                "indexes": indexes,
            },
        )

        def __str__(self):
            """
            When the model instance is rendered to a string, then we want to return the
            primary field value in human readable format.
            """

            field = self._field_objects.get(self._primary_field_id, None)

            if not field:
                return f"unnamed row {self.id}"

            return field["type"].get_human_readable_value(
                getattr(self, field["name"]), field
            )

        attrs = {
            "Meta": meta,
            "__module__": "database.models",
            # An indication that the model is a generated table model.
            "_generated_table_model": True,
            "baserow_table": self,
            "baserow_table_id": self.id,
            "baserow_models": apps.baserow_models,
            # We are using our own table model manager to implement some queryset
            # helpers.
            "objects": TableModelManager(),
            "objects_and_trash": TableModelTrashAndObjectsManager(),
            "__str__": __str__,
        }

        use_cache = (
            use_cache
            and len(fields) == 0
            and field_ids is None
            and add_dependencies is True
            and attribute_names is False
            and not settings.BASEROW_DISABLE_MODEL_CACHE
        )

        if use_cache:
            # We don't need to refresh the version if it has already been refreshed for
            # this session.
            local_cache.get(
                f"database_table_model_{self.id}_refreshed",
                lambda: self.refresh_from_db(fields=["version"]),
            )
            field_attrs = get_cached_model_field_attrs(self)
        else:
            field_attrs = None

        if field_attrs is None:
            field_attrs = self._fetch_and_generate_field_attrs(
                add_dependencies,
                attribute_names,
                field_ids,
                field_names,
                fields,
                filtered,
            )

            if use_cache:
                set_cached_model_field_attrs(self, field_attrs)
        else:
            # We found cached model fields, they will have a cached creation_counter
            # attribute each used to compare model fields to do django
            # fundamental internal operations like generating SQL to select from this
            # table. Any new model fields added to this table will use a global
            # static counter on the Model class itself. To prevent any possibility
            # of collisions between the model fields that just came out of the cache
            # and these new model fields we are about to init below, we increase
            # this global creation_counter to prevent any possible collision and
            # horrible bugs.
            max_creation_counter_from_cache = DjangoModelFieldClass.creation_counter
            for f in field_attrs.values():
                if isinstance(f, DjangoModelFieldClass) and not f.auto_created:
                    max_creation_counter_from_cache = max(
                        max_creation_counter_from_cache,
                        getattr(f, "creation_counter", max_creation_counter_from_cache),
                    )
            DjangoModelFieldClass.creation_counter = max_creation_counter_from_cache + 1

        # We have to add the order field after reading the potentially cached values
        # as those cached model fields will have a cached creation_counter and we need
        # to ensure any other model fields added to this same model are __init__ed
        # after we've fixed the global DjangoModelFieldClass.creation_counter
        # above.
        field_attrs["order"] = models.DecimalField(
            max_digits=40,
            decimal_places=20,
            editable=False,
            default=1,
        )
        if self.needs_background_update_column_added:
            self._add_needs_background_update_column(field_attrs, indexes)

        if self.created_by_column_added:
            self._add_created_by(field_attrs, indexes)

        if self.last_modified_by_column_added:
            self._add_last_modified_by(field_attrs, indexes)

        if self.field_rules_validity_column_added:
            self._add_field_rules_valid(field_attrs, indexes)

        attrs.update(**field_attrs)

        # Create the model class.
        model = type(
            str(model_name),
            (
                GeneratedTableModel,
                TrashableModelMixin,
                CreatedAndUpdatedOnMixin,
                models.Model,
            ),
            attrs,
        )

        patch_meta_get_field(model._meta)

        if not manytomany_models:
            self._after_model_generation(attrs, model)

        return model

    def _add_needs_background_update_column(self, field_attrs, indexes):
        field_attrs[ROW_NEEDS_BACKGROUND_UPDATE_COLUMN_NAME] = BooleanField(
            default=False,
            help_text="DEPRECATED: remove in a future version when all "
            "tsvectors columns will be removed",
        )

    def _add_created_by(self, field_attrs, indexes):
        field_attrs[CREATED_BY_COLUMN_NAME] = IgnoreMissingForeignKey(
            User,
            null=True,
            related_name="+",
            related_query_name="+",
            db_constraint=False,
            on_delete=models.DO_NOTHING,
            help_text="Stores information about the user that created the row.",
        )

    def _add_last_modified_by(self, field_attrs, indexes):
        field_attrs[LAST_MODIFIED_BY_COLUMN_NAME] = IgnoreMissingForeignKey(
            User,
            null=True,
            related_name="+",
            related_query_name="+",
            db_constraint=False,
            on_delete=models.DO_NOTHING,
            help_text="Stores information about the user that modified the row last.",
        )

    def _add_field_rules_valid(self, field_attrs, indexes):
        from baserow.contrib.database.field_rules.handlers import FieldRuleHandler

        column = FieldRuleHandler.get_state_column()
        field_attrs[FieldRuleHandler.STATE_COLUMN_NAME] = column
        return field_attrs

    @baserow_trace(tracer)
    def _after_model_generation(self, attrs, model):
        # In some situations the field can only be added once the model class has been
        # generated. So for each field we will call the after_model_generation with
        # the generated model as argument in order to do this. This is for example used
        # by the link row field. It can also be used to make other changes to the
        # class.
        all_field_objects = {
            **attrs["_field_objects"],
            **attrs["_trashed_field_objects"],
        }
        for field_object in all_field_objects.values():
            field_object["type"].after_model_generation(
                field_object["field"], model, field_object["name"]
            )

    @baserow_trace(tracer)
    def _fetch_and_generate_field_attrs(
        self,
        add_dependencies,
        attribute_names,
        field_ids,
        field_names,
        fields,
        filtered,
    ):
        field_attrs = {
            "_primary_field_id": -1,
            # An object containing the table fields, field types and the chosen
            # names with the table field id as key.
            "_field_objects": {},
            # An object containing the trashed table fields, field types and the
            # chosen names with the table field id as key.
            "_trashed_field_objects": {},
        }
        # Construct a query to fetch all the fields of that table. We need to
        # include any trashed fields so the created model still has them present
        # as the column is still actually there. If the model did not have the
        # trashed field attributes then model.objects.create will fail as the
        # trashed columns will be given null values by django triggering not null
        # constraints in the database.
        fields_query = (
            self.field_set(manager="objects_and_trash")
            .select_related("table__database__workspace", "content_type")
            .all()
        )

        # If the field ids are provided we must only fetch the fields of which the
        # ids are in that list.
        if isinstance(field_ids, list):
            if len(field_ids) == 0:
                fields_query = []
            else:
                fields_query = fields_query.filter(pk__in=field_ids)

        # If the field names are provided we must only fetch the fields of which the
        # user defined name is in that list.
        if isinstance(field_names, list):
            if len(field_names) == 0:
                fields_query = []
            else:
                fields_query = fields_query.filter(name__in=field_names)

        if isinstance(fields_query, QuerySet):
            fields_query = specific_iterator(
                fields_query,
                per_content_type_queryset_hook=(
                    lambda model, queryset: field_type_registry.get_by_model(
                        model
                    ).enhance_field_queryset(queryset, model)
                ),
            )

        # Create a combined list of fields that must be added and belong to the this
        # table.
        fields = list(fields) + [field for field in fields_query]

        # If there are duplicate field names we have to store them in a list so we
        # know later which ones are duplicate.
        duplicate_field_names = []
        already_included_field_names = set([f.name for f in fields])

        # We will have to add each field to with the correct field name and model
        # field to the attribute list in order for the model to work.
        while len(fields) > 0:
            field = fields.pop(0)
            trashed = field.trashed
            field = field.specific
            field_type = field_type_registry.get_by_model(field)
            field_name = field.db_column

            if filtered and add_dependencies:
                from baserow.contrib.database.fields.dependencies.handler import (
                    FieldDependencyHandler,
                )

                direct_dependencies = (
                    FieldDependencyHandler.get_same_table_dependencies(field)
                )
                for f in direct_dependencies:
                    if f.name not in already_included_field_names:
                        fields.append(f)
                        already_included_field_names.add(f.name)

            # If attribute_names is True we will not use 'field_{id}' as attribute
            # name, but we will rather use a name the user provided.
            if attribute_names:
                field_name = field.model_attribute_name
                if trashed:
                    field_name = f"trashed_{field_name}"
                # If the field name already exists we will append '_field_{id}' to
                # each entry that is a duplicate.
                if field_name in field_attrs:
                    duplicate_field_names.append(field_name)
                    replaced_field_name = (
                        f"{field_name}_{field_attrs[field_name].db_column}"
                    )
                    field_attrs[replaced_field_name] = field_attrs.pop(field_name)
                if field_name in duplicate_field_names:
                    field_name = f"{field_name}_{field.db_column}"

            field_objects_dict = (
                "_trashed_field_objects" if trashed else "_field_objects"
            )
            # Add the generated objects and information to the dict that
            # optionally can be returned. We exclude trashed fields here so they
            # are not displayed by baserow anywhere.
            field_attrs[field_objects_dict][field.id] = {
                "field": field,
                "type": field_type,
                "name": field_name,
            }
            if field.primary:
                field_attrs["_primary_field_id"] = field.id
            # Add the field to the attribute dict that is used to generate the
            # model. All the kwargs that are passed to the `get_model_field`
            # method are going to be passed along to the model field.
            field_attrs[field_name] = field_type.get_model_field(
                field,
                db_column=field.db_column,
                verbose_name=field.name,
            )

        return field_attrs

    # Use our own custom index name as the default models.Index
    # naming scheme causes 5+ collisions on average per 1000 new
    # tables.
    def get_collision_safe_order_id_idx_name(self):
        return f"tbl_order_id_{self.id}_idx"


class DuplicateTableJob(
    JobWithUserIpAddress, JobWithWebsocketId, JobWithUndoRedoIds, Job
):
    original_table = models.ForeignKey(
        Table,
        null=True,
        related_name="duplicated_by_jobs",
        on_delete=models.SET_NULL,
        help_text="The Baserow table to duplicate.",
    )

    duplicated_table = models.OneToOneField(
        Table,
        null=True,
        related_name="duplicated_from_jobs",
        on_delete=models.SET_NULL,
        help_text="The duplicated Baserow table.",
    )


class RichTextFieldMention(models.Model):
    table = models.ForeignKey(
        Table,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="The table that the user mention is in.",
    )
    row_id = models.PositiveIntegerField(
        help_text="The row id that the user mention is in."
    )
    field = models.ForeignKey(
        "database.Field",
        on_delete=models.CASCADE,
        related_name="+",
        help_text="The field that the user mention is in.",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="+",
        help_text="The user that is mentioned.",
    )
    marked_for_deletion_at = models.DateTimeField(
        null=True,
        db_index=True,
        help_text="The date and time that the mention has been marked as ready for deletion.",
    )

    class Meta:
        unique_together = ("table", "row_id", "field", "user")
        indexes = [
            models.Index(fields=["row_id", "field"]),
        ]
