import contextlib
import random
import time
from collections import defaultdict
from decimal import Decimal
from functools import cache, wraps
from math import ceil
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import DEFAULT_DB_ALIAS, OperationalError, connection, transaction
from django.db.models import ForeignKey, ManyToManyField, Max, Model, Prefetch, QuerySet
from django.db.models.functions import Collate
from django.db.models.query import ModelIterable
from django.db.models.sql.query import LOOKUP_SEP
from django.db.transaction import Atomic, get_connection

from loguru import logger

from baserow.core.exceptions import DeadlockException
from baserow.core.psycopg import is_deadlock_error, sql

from .utils import find_intermediate_order

ModelInstance = TypeVar("ModelInstance", bound=object)


def get_database_dsn() -> str:
    """
    Constructs the database DSN from the default database settings.

    :return: The database DSN as a string.
    """

    db = settings.DATABASES["default"]
    return f"postgres://{db['USER']}:{db['PASSWORD']}@{db['HOST']}:{db['PORT']}/{db['NAME']}"


class LockedAtomicTransaction(Atomic):
    """
    Does a atomic transaction, but also locks the entire table for any transactions,
    for the duration of this transaction. Although this is the only way to avoid
    concurrency issues in certain situations, it should be used with caution,
    since it has impacts on performance, for obvious reasons...
    """

    def __init__(self, model, using=None, savepoint=True, durable=False):
        if using is None:
            using = DEFAULT_DB_ALIAS

        super().__init__(using, savepoint, durable)
        self.model = model

    def __enter__(self):
        super(LockedAtomicTransaction, self).__enter__()

        cursor = None
        try:
            cursor = get_connection(self.using).cursor()
            cursor.execute(
                "LOCK TABLE {db_table_name}".format(
                    db_table_name=self.model._meta.db_table
                )
            )
        finally:
            if cursor and not cursor.closed:
                cursor.close()

    def __exit__(self, *args, **kwargs):
        return super().__exit__(*args, **kwargs)


T = TypeVar("T", bound=Model)


def specific_iterator(
    queryset_or_list: QuerySet[T] | Iterable[T],
    per_content_type_queryset_hook: Callable[[T, QuerySet[T]], QuerySet[T]]
    | None = None,
    base_model: T | None = None,
    select_related: List[str] = None,
    skip_missing_specific_objects: bool = False,
) -> List[T]:
    """
    Iterates over the given queryset or list of model instances, and finds the specific
    objects with the least amount of queries. If a queryset is provided respects the
    annotations, select related and prefetch related of the provided query. This
    function is only compatible with models having the `PolymorphicContentTypeMixin`
    and `content_type` property.

    Can be used like:

    for specific_object in specific_iterator(Application.objects.all()):
        print(type(specific_object))  # Database

    :param queryset_or_list: The queryset to the base model of which we want to select
        the specific types from. Alternatively, a list of model instances can be
        provided of they're already resolved. This can be useful if the instances are
        fetched via a `select_related` for example.
    :param per_content_type_queryset_hook: If provided, it will be called for every
        specific queryset to allow extending it.
    :param base_model: The base model must be provided if a list is provided in the
        `queryset_or_list` argument.
    :param select_related: A `select_related` list can optionally be provided if a list
        is provided in the `queryset_or_list` argument. This should be used if the
        instances provided in the list have select related objects.
    :return: A list of specific objects in the right order.
    :param skip_missing_specific_objects: When True, missing specific instances
        are logged without raising an error.
    """

    if isinstance(queryset_or_list, QuerySet):
        # Figure out beforehand what the annotation keys and select related keys are.
        # This way, we can later set those properties on the specific objects.
        annotation_keys = queryset_or_list.query.annotations.keys()
        select_related = queryset_or_list.query.select_related

        if isinstance(select_related, bool):
            select_related_keys = []
        else:
            select_related_keys = list(select_related.keys())

        # Nested prefetch result in cached objects to avoid additional queries. If
        # they're present, they must be added to the `select_related_keys` to make sure
        # they're correctly set on the specific objects.
        for lookup in queryset_or_list._prefetch_related_lookups:
            if isinstance(lookup, Prefetch):
                lookup = lookup.prefetch_through
            split_lookup = lookup.split(LOOKUP_SEP)[:-1]
            if split_lookup and split_lookup[0] not in select_related_keys:
                select_related_keys.append(split_lookup[0])

        # The original queryset must resolved because we need the pk, content type,
        # annotated data and selected related data. By forcing it to resolve early on,
        # we prevent accidentally resolving it multiple times.
        base_model = queryset_or_list.model
        resolved_queryset = list(queryset_or_list)
    else:
        if base_model is None:
            raise ValueError(
                "The `base_model` must be provided if iterating over a list."
            )

        annotation_keys = []
        select_related_keys = [] if select_related is None else select_related
        resolved_queryset = queryset_or_list

    types_and_pks = defaultdict(list)
    for item in resolved_queryset:
        content_type = ContentType.objects.get_for_id(item.content_type_id)
        types_and_pks[content_type].append(item.id)

    # Fetch the specific objects by executing a single query for each unique content
    # type and construct a mapping containing them by id.
    specific_objects = {}
    for content_type, pks in types_and_pks.items():
        model = content_type.model_class() or base_model
        # We deliberately want to use the `_base_manager` here so it's works exactly
        # the same as the `.specific` property and so that trashed objects will still
        # be fetched.
        objects = model._base_manager.filter(pk__in=pks)

        if per_content_type_queryset_hook is not None:
            objects = per_content_type_queryset_hook(model, objects)

        for obj in objects:
            specific_objects[obj.id] = obj

    # Create an array with specific objects in the right order.
    ordered_specific_objects = []
    for item in resolved_queryset:
        # If the specific object is not found, but the base object is, it means that
        # there is a data integrity error. In that case, we want to fail hard.
        try:
            specific_object = specific_objects[item.id]
        except KeyError:
            error = f"The specific object with id {item.id} does not exist."

            if skip_missing_specific_objects:
                logger.error(error)
                continue

            raise base_model.DoesNotExist(error)

        # If there are annotation keys, we must extract them from the original item
        # because they should exist there and set them on the specific object so they
        # can be used from there.
        if annotation_keys:
            for annotation_key in annotation_keys:
                if hasattr(item, annotation_key):
                    setattr(
                        specific_object, annotation_key, getattr(item, annotation_key)
                    )

        if select_related_keys:
            for select_related_key in select_related_keys:
                if hasattr(item, select_related_key):
                    setattr(
                        specific_object,
                        select_related_key,
                        getattr(item, select_related_key),
                    )

        # If the original item has the `_prefetched_objects_cache` object, it means that
        # the `prefetch_related` was used and fetched on the base queryset. By
        # setting it on the specific object, we move that prefetched data over so
        # that we don't have to execute the same query again.
        if hasattr(item, "_prefetched_objects_cache"):
            specific_prefetched_objects_cache = getattr(
                specific_object, "_prefetched_objects_cache", {}
            )
            specific_object._prefetched_objects_cache = {
                **item._prefetched_objects_cache,
                **specific_prefetched_objects_cache,
            }

        ordered_specific_objects.append(specific_object)

    return ordered_specific_objects


def specific_queryset(
    queryset: QuerySet[T],
    per_content_type_queryset_hook: Callable[[T, QuerySet[T]], QuerySet[T]]
    | None = None,
) -> QuerySet[T]:
    """
    Applies an iterable to the queryset that calls the `specific_iterator` when the
    queryset resolves. This allows for modifying the queryset, even after marking the
    queryset as a specific.

    This is particularly useful in combination with the `Prefetch` class for example.

    Can be used like:

    queryset = specific_queryset(
        Field.objects.all()
    ).filter(id__in=[1, 2])

    :param queryset: The queryset which we want to select the specific types from.
    :param per_content_type_queryset_hook: If provided, it will be called for every
        specific queryset to allow extending it.
    :return: A queryset that will resolve to specific objects.
    """

    clone = queryset._clone()

    class SpecificIterable(clone._iterable_class):
        def __iter__(self):
            queryset = self.queryset

            select_related = queryset.query.select_related

            if isinstance(select_related, bool):
                select_related_keys = []
            else:
                select_related_keys = select_related.keys()

            model = queryset.model
            rows = list(super().__iter__())
            for specific_row in specific_iterator(
                queryset_or_list=rows,
                per_content_type_queryset_hook=per_content_type_queryset_hook,
                base_model=model,
                select_related=select_related_keys,
            ):
                yield specific_row

    clone._iterable_class = SpecificIterable

    return clone


class IsolationLevel:
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


@contextlib.contextmanager
def transaction_atomic(
    using=None,
    savepoint=True,
    durable=False,
    isolation_level: Optional[str] = None,
    first_sql_to_run_in_transaction_with_args: Optional[
        Tuple[sql.SQL, List[Any]]
    ] = None,
):
    with transaction.atomic(using, savepoint, durable) as a:
        if isolation_level or first_sql_to_run_in_transaction_with_args:
            cursor = get_connection(using).cursor()

            if isolation_level:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL %s" % isolation_level)

            if first_sql_to_run_in_transaction_with_args:
                first_sql, first_args = first_sql_to_run_in_transaction_with_args
                cursor.execute(first_sql.format(*first_args))
        yield a


def get_unique_orders_before_item(
    before: Model,
    queryset: QuerySet,
    amount: int = 1,
    field: str = "order",
) -> List[Decimal]:
    """
    Calculates a list of unique decimal orders that can safely be used before the
    provided `before`.

    :param before: The model instance where the before orders must be
        calculated for.
    :param queryset: The base queryset used to compute the value.
    :param amount: The number of orders that must be requested. Can be higher if
        multiple items are inserted or moved.
    :raises CannotCalculateIntermediateOrder: If it's not possible to recalculate an
        intermediate order. The full order of the items must be recalculated in this
        case before calling this function again.
    :return: A list of decimals containing safe to use orders in order.
    """

    # In order to find the intermediate order, we need to figure out what the
    # order of the before adjacent row is. This queryset finds it in an
    # efficient way.
    adjacent_order = (
        queryset.filter(order__lt=before.order).aggregate(max=Max(field)).get("max")
    ) or Decimal("0")
    new_orders = []
    new_order = adjacent_order
    for i in range(0, amount):
        float_order = find_intermediate_order(new_order, before.order)
        # Row orders "only" store 20 decimal places. We're already rounding it,
        # so that the `order` will be set immediately.
        new_order = round(Decimal(float_order), 20)
        new_orders.append(new_order)
    return new_orders


def get_highest_order_of_queryset(
    queryset: QuerySet,
    amount: int = 1,
    field: str = "order",
) -> List[Decimal]:
    """
    Returns the highest existing values of the provided order field.

    :param queryset: The queryset containing the field to check.
    :param amount: The amount of order to return.
    :param field: The field name containing the value.
    :return: A list of highest order value in the queryset.
    """

    step = Decimal("1.00000000000000000000")
    last_order = ceil(queryset.aggregate(max=Max(field)).get("max") or Decimal("0"))
    return [last_order + (step * i) for i in range(1, amount + 1)]


def recalculate_full_orders(
    model: Optional[Model] = None,
    field="order",
    queryset: Optional[QuerySet] = None,
):
    """
    Recalculates the order to whole numbers of all instances based on the existing
    position.

    id     old_order    new_order
    1      1.5000       2.0000
    2      1.7500       3.0000
    3      0.7500       1.0000

    :param model: The model we want to reorder the instance for.
    :param field: The order field name.
    :param queryset: An optional queryset to filter the item orders that are
        recalculated. This queryset must select all the item to recalculate.
    """

    table_name = model.objects.model._meta.db_table
    ordering = model._meta.ordering

    if queryset:
        item_ids = queryset.values_list("id", flat=True)
        where_clause = sql.SQL("where c2.id in ({id_list})").format(
            id_list=sql.SQL(", ").join([sql.Literal(item_id) for item_id in item_ids])
        )
    else:
        where_clause = sql.SQL("")

    # Unfortunately, it's not possible to do this via the Django ORM. I've
    # tried various ways, but ran into "Window expressions are not allowed" or
    # 'NoneType' object has no attribute 'get_source_expressions' errors.
    # More information can be found here:
    # https://stackoverflow.com/questions/66022483/update-django-model-based-on-the-row-number-of-rows-produced-by-a-subquery-on-th
    #
    # model.objects_and_trash.annotate(
    #     row_number=Window(
    #         expression=RowNumber(),
    #         order_by=[F(order) for order in model._meta.ordering],
    #         )
    #     ).update(order=F('row_number')
    # )
    raw_query = """
        update {table_name} c1
            set {order_field} = c2.seqnum from (
            select c2.*, row_number() over (
                ORDER BY {order_params}
            ) as seqnum from {table_name} c2 {where_clause}
            ) c2
        where c2.id = c1.id"""
    with connection.cursor() as cursor:
        sql_query = sql.SQL(raw_query).format(
            order_field=sql.Identifier(field),
            table_name=sql.Identifier(table_name),
            order_params=sql.SQL(", ").join(
                [
                    sql.SQL(".").join([sql.Identifier("c2"), sql.Identifier(o)])
                    for o in ordering
                ]
            ),
            where_clause=where_clause,
        )
        cursor.execute(sql_query)


@cache
def get_collation_name() -> Optional[str]:
    """
    Performs a simple check to determine if expected Baserow collation
    can be used by sourcing pg_collation table.

    Returns the name of the Baserow collation if it
    can be used, None otherwise.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT collname FROM pg_collation where collname = %s AND collencoding = -1",
            [settings.EXPECTED_COLLATION],
        )
        row = cursor.fetchone()
        if row is None:
            logger.warning(
                f"Database collation '{settings.EXPECTED_COLLATION}' cannot be used."
                " This might result in unexpected behavior. Please configure your"
                " database appropriately."
            )
        return settings.EXPECTED_COLLATION if row else None


def collate_expression(expression):
    """
    If default Baserow collation can be used
    the provided expression will be collated.
    If not, the original expression is returned.
    """

    coll_name = get_collation_name()
    return Collate(expression, coll_name) if coll_name else expression


class MultiFieldPrefetchQuerysetMixin(Generic[ModelInstance]):
    """
    This mixin introduces a `multi_field_prefetch` method that can be used to
    register a function to modify the `result_cache`. This can be used to prefetch
    data in a more advanced way, for example when prefetching data for two fields in
    one single query.

    def prefetch_example(results):
        print('will be called')

    Model.objects.all().prefetch_example(prefetch_example)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._multi_field_prefetch_related_funcs = []
        self._multi_field_prefetch_done = False

    def _fetch_all(self):
        super()._fetch_all()
        if (
            self._multi_field_prefetch_related_funcs
            and not self._multi_field_prefetch_done
            and issubclass(self._iterable_class, ModelIterable)
        ):
            for f in self._multi_field_prefetch_related_funcs:
                f(self, self._result_cache)
            self._multi_field_prefetch_done = True

    def _clone(self, *args, **kwargs):
        c = super()._clone(*args, **kwargs)
        c._multi_field_prefetch_related_funcs = (
            self._multi_field_prefetch_related_funcs[:]
        )
        return c

    def multi_field_prefetch(
        self, custom_prefetch_function: Callable[[QuerySet, List[ModelInstance]], None]
    ):
        clone = self._chain()
        clone._multi_field_prefetch_related_funcs.append(custom_prefetch_function)
        return clone

    def clear_multi_field_prefetch(self):
        clone = self._chain()
        clone._multi_field_prefetch_related_funcs = []
        return clone

    def get_multi_field_prefetches(self):
        return self._multi_field_prefetch_related_funcs


class CombinedForeignKeyAndManyToManyMultipleFieldPrefetch:
    """
    This prefetch class can be used as argument of the `multi_field_prefetch` method.
    It allows setting multiple fields foreignkey or manytomany fields are argument,
    as long as they have the same `target_model` as relationship. For N number of
    fields, it will execute a maximum of 2 queries to prefetch all the related results.

    Example:

    results = list(
        model
        .objects.all()
        .multi_field_prefetch(
            CombinedForeignKeyAndManyToManyMultipleFieldPrefetch(SelectOption)
            .add_field_names("field_1", "field_2")
        )
    )

    results[0].field_1  # is prefetched
    results[0].field_2  # is prefetched
    results[1].field_1  # is prefeetched
    ...
    """

    def __init__(
        self,
        target_model: Model,
        field_names: Optional[Set] = None,
        skip_target_check: Optional[bool] = False,
    ):
        """
        :param target_model: The model where the final prefetch query, to fetch the
            instances, will be executed on. All the `field_names` must have a
            relationship with that model.
        :param field_names: The names of the fields that must be included in the
            prefetch query.
        :param skip_target_check: Disables the check if the field is compatible with
            the target model. Warning: only use this if you're working with dynamic
            models, and if you know what you're doing!
        """

        self.field_names = set(field_names or [])
        self.target_model = target_model
        self.skip_target_check = skip_target_check

    def add_field_names(self, field_names: List[str]):
        """
        This method allows adding additional field names to the prefetch. This can be
        useful in a scenario where you dynamically want to add more fields.

        :param field_names: The names of the fields that must be included in the
            prefetch query.
        :return: Self to allow chaining.
        """

        self.field_names.update(field_names)
        return self

    def __call__(self, queryset: QuerySet, result_set: List[ModelInstance]):
        """
        This method is called when the queryset resolved. It's responsible for
        collecting which ids must be prefetched.

        :param queryset: The queryset that is being resolved.
        :param result_set: The fetched `result_set` where the prefetched results must
            be added to.
        """

        row_id_to_field_name_to_target_ids = defaultdict(lambda: defaultdict(list))

        row_id_to_field_name_to_target_ids = self.collect_foreign_key_target_ids(
            queryset, result_set, row_id_to_field_name_to_target_ids
        )
        row_id_to_field_name_to_target_ids = self.collect_many_to_many_key_target_ids(
            queryset, result_set, row_id_to_field_name_to_target_ids
        )

        target_instances = self.fetch_target_instances(
            row_id_to_field_name_to_target_ids
        )
        self.set_prefetched_values_on_result_set(
            queryset, row_id_to_field_name_to_target_ids, result_set, target_instances
        )

    def set_prefetched_values_on_result_set(
        self,
        queryset,
        row_id_to_field_name_to_target_ids: Dict[int, Dict[str, List]],
        result_set: List[ModelInstance],
        target_instances: Dict[int, ModelInstance],
    ) -> List[ModelInstance]:
        """
        Sets the prefetched instances on the result set of the queryset. It will
        figure out if the original field was a foreign key or a many to many field,
        and will apply the instances accordingly.

        :param queryset: The queryset that is being resolved.
        :param row_id_to_field_name_to_target_ids: A mapping that contains which id
            in the target model belongs to which row and field id.
        :param result_set: The fetched `result_set` where the prefetched results must
            be added to. This also contains the foreign key ids.
        :param target_instances: The fetched target instances that must be applied to
            the `result_set`.
        :return: The updated `result_set` containing all the prefetched instances.
        """

        for result in result_set:
            for field_name in self.field_names:
                model_field = queryset.model._meta.get_field(field_name)
                target_ids = row_id_to_field_name_to_target_ids[result.id].get(
                    field_name
                )

                if isinstance(model_field, ForeignKey) and target_ids is not None:
                    target_id = target_ids[0]
                    target_instance = target_instances.get(target_id)
                    setattr(result, field_name, target_instance)

                if isinstance(model_field, ManyToManyField):
                    attr = getattr(result, field_name)
                    qs = attr.get_queryset()
                    qs._result_cache = (
                        [
                            target_instances.get(target_id)
                            for target_id in target_ids
                            # It could be that the target doesn't exist, but the
                            # relationship does. In that case, we don't want the
                            # result set contain `None` values.
                            if target_id in target_instances
                        ]
                        if target_ids
                        else []
                    )
                    qs._prefetch_done = True
                    result._prefetched_objects_cache = getattr(
                        result, "_prefetched_objects_cache", {}
                    )
                    result._prefetched_objects_cache[field_name] = qs

        return result_set

    def fetch_target_instances(
        self, row_id_to_field_name_to_target_ids: Dict[int, Dict[str, List]]
    ) -> Dict[int, ModelInstance]:
        """
        Fetches all the instances of the collected ids in the target model in one
        efficient query.

        :param row_id_to_field_name_to_target_ids: A mapping that contains which id
            in the target model belongs to which row and field id.
        :return: The fetched instances in a dict where the key is the instance id.
        """

        all_target_ids = {
            id
            for field_names in row_id_to_field_name_to_target_ids.values()
            for target_ids in field_names.values()
            for id in target_ids
        }
        # We only want to fetch the instances that are actually present in the
        # resolved queryset to avoid fetching unnecessary instances.
        target_instances = {
            instance.id: instance
            for instance in self.target_model.objects.filter(id__in=all_target_ids)
        }
        return target_instances

    def collect_foreign_key_target_ids(
        self,
        queryset: QuerySet,
        result_set: List[ModelInstance],
        row_id_to_field_name_to_target_ids: Dict[int, Dict[str, List]],
    ):
        """
        Loops over all already fetched rows of the original queryset, and collects the
        foreign key ids of the provided `field_names`.

        :param queryset: The queryset that is being resolved.
        :param result_set: The fetched `result_set` where the prefetched results must
            be added to. This also contains the foreign key ids.
        :param row_id_to_field_name_to_target_ids: A mapping that contains which id
            in the target model belongs to which row and field id.
        :return: An updated mapping, now also containing the foreign key ids.
        """

        foreign_key_names = set()

        for field_name in self.field_names:
            model_field = queryset.model._meta.get_field(field_name)

            if not isinstance(model_field, ForeignKey):
                continue

            if (
                not self.skip_target_check
                and model_field.remote_field.model is not self.target_model
            ):
                raise ValueError(
                    f"The related model of {field_name} is not equal to the target "
                    f"model {self.target_model}."
                )

            foreign_key_names.add(field_name)

        for result in result_set:
            for field_name in foreign_key_names:
                value = getattr(result, f"{field_name}_id")

                if value is not None:
                    row_id_to_field_name_to_target_ids[result.id][field_name].append(
                        value
                    )

        return row_id_to_field_name_to_target_ids

    def collect_many_to_many_key_target_ids(
        self, queryset: QuerySet, result_set, row_id_to_field_name_to_target_ids
    ):
        """
        Loops over all already fetched rows of the original queryset, and collects the
        many to many ids of the provided `field_names`. Even though each many to many
        field has its own through table, it's combined into multiple union queries,
        send to the server as one query.

        :param queryset: The queryset that is being resolved.
        :param result_set: The fetched `result_set` where the prefetched results must
            be added to. This also contains the foreign key ids.
        :param row_id_to_field_name_to_target_ids: A mapping that contains which id
            in the target model belongs to which row and field id.
        :return: An updated mapping, now also containing the many to many ids.
        """

        sub_queries = []
        row_ids_as_literal = [sql.Literal(str(result.id)) for result in result_set]

        for field_name in self.field_names:
            model_field = queryset.model._meta.get_field(field_name)

            if not isinstance(model_field, ManyToManyField):
                continue

            through_model = model_field.remote_field.through
            through_table_name = through_model._meta.db_table
            through_fields = through_model._meta.get_fields()
            row_column_name = through_fields[1].get_attname_column()[1]
            target_column_name = through_fields[2].get_attname_column()[1]

            if (
                not self.skip_target_check
                and through_fields[2].remote_field.model is not self.target_model
            ):
                raise ValueError(
                    f"The related model of {field_name} is not equal to the target "
                    f"model {self.target_model}."
                )

            subquery = sql.SQL(
                """
                (
                    SELECT
                        id,
                        {field_name} as field_name,
                        {row_id_column} as row_id,
                        {target_id_column} as target_id_column
                    FROM {m2m_table}
                    WHERE {row_id_column} IN ({row_ids})
                )
                """
            ).format(
                field_name=sql.Literal(field_name),
                m2m_table=sql.Identifier(through_table_name),
                row_id_column=sql.Identifier(row_column_name),
                target_id_column=sql.Identifier(target_column_name),
                row_ids=sql.SQL(",").join(row_ids_as_literal),
            )
            sub_queries.append(subquery)

        if len(sub_queries) > 0 and len(result_set) > 0:
            union_query = sql.SQL(" UNION ").join(sub_queries)
            union_sql = sql.SQL(
                """
                SELECT
                    row_id,
                    field_name,
                    ARRAY_AGG(target_id_column ORDER BY id)
                FROM ({union_query}) sub
                GROUP BY row_id, field_name
                """
            ).format(union_query=union_query)

            with connection.cursor() as cursor:
                cursor.execute(union_sql)
                results = cursor.fetchall()

            for result in results:
                # 0=row_id, 1=field_name, 2=target ids
                row_id_to_field_name_to_target_ids[result[0]][result[1]] = result[2]

        return row_id_to_field_name_to_target_ids


def atomic_with_retry_on_deadlock(
    max_retries: Optional[int] = None,
    initial_backoff: Optional[float] = None,
    jitter: Optional[float] = 1.0,
):
    """
    Decorator that wraps a function in a transaction.atomic block and retries
    when deadlock occurswith exponential backoff.

    The decorated function must be idempotent - it should be safe to retry multiple
    times without changing behavior. Avoid modifying request.data or other mutable
    state that could cause retries to behave differently from the original attempt.

    :param max_retries: Maximum number of retry attempts
    :param initial_backoff: Initial backoff time in seconds
    :param jitter: Jitter factor to randomize the backoff time
    """

    if max_retries is None:
        max_retries = settings.BASEROW_DEADLOCK_MAX_RETRIES
    if initial_backoff is None:
        initial_backoff = settings.BASEROW_DEADLOCK_INITIAL_BACKOFF

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0
            backoff = initial_backoff + random.uniform(0, jitter)  # nosec: B311

            while retries <= max_retries:
                try:
                    with transaction.atomic():
                        return func(*args, **kwargs)
                except OperationalError as exc:
                    if not is_deadlock_error(exc):
                        raise exc

                    if retries == max_retries:
                        logger.exception(
                            "Deadlock detected while committing transaction",
                        )
                        raise DeadlockException() from exc
                    time.sleep(backoff)
                    logger.debug("Retrying transaction after deadlock")
                    backoff *= 1.5 + random.uniform(0, jitter)  # nosec: B311
                retries += 1

        return wrapper

    return decorator
