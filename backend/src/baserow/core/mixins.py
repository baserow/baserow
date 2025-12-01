import abc
from decimal import Decimal
from typing import Callable, Generic, List, Optional, TypeVar

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Case, QuerySet, Value, When
from django.db.models.fields import NOT_PROVIDED
from django.db.models.fields.mixins import FieldCacheMixin
from django.utils.functional import cached_property

from django_cte import CTEManager

from baserow.core.db import (
    get_highest_order_of_queryset,
    get_unique_orders_before_item,
    recalculate_full_orders,
)
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.fields import SyncedDateTimeField
from baserow.core.managers import NoTrashManager, TrashOnlyManager, make_trash_manager
from baserow.core.registry import Instance, ModelRegistryMixin


class OrderableMixin:
    """
    This mixin introduces a set of helpers of the model is orderable by a field.
    """

    @classmethod
    def get_highest_order_of_queryset(
        cls, queryset: QuerySet, field: str = "order"
    ) -> int:
        """
        Returns the highest existing value of the provided field.

        :param queryset: The queryset containing the field to check.
        :param field: The field name containing the value.
        :return: The highest value in the queryset.
        """

        return queryset.aggregate(models.Max(field)).get(f"{field}__max", 0) or 0

    @classmethod
    def order_objects(
        cls, queryset: QuerySet, new_order: List[int], field: str = "order"
    ) -> List[int]:
        """
        Changes the order of the objects in the given queryset to the desired order
        provided in the new_order parameter. The new_order list can be a subset
        of all object ids to order. In this case, this function applies the best effort
        to respect the new order while keeping the rest of the ordered objects as
        close as they were before.

        :param queryset: The queryset of the objects that need to be updated.
        :param new_order: A list containing the object ids in the desired order. This
            list can be partial.
        :param field: The name of the order column/field.
        :raises IdDoesNotExist: If any of the new order ids provided do not exist in
            the queryset provided
        :return: The full ordered list of ids.
        """

        new_order = list(new_order)
        previous_full_id_order = list(queryset.values_list("id", flat=True))

        for new_order_id in new_order:
            if new_order_id not in previous_full_id_order:
                raise IdDoesNotExist(new_order_id)

        new_full_order = []
        current = 0

        # Support order with partial input list
        while previous_full_id_order:
            obj_id = previous_full_id_order[current]

            # obj_id not in new order, let's append it
            if obj_id not in new_order:
                previous_full_id_order.pop(current)
                new_full_order.append(obj_id)
                current = 0
            # obj_id is equal to first element of new_order, let's append it
            elif obj_id == new_order[0]:
                previous_full_id_order.pop(current)
                new_full_order.append(obj_id)
                new_order.pop(0)
                current = 0
            # obj_id is in the list but it's not the first element. Then skip it for
            # now but let's take a look at the next id
            else:
                current += 1

        queryset.update(
            **{
                field: Case(
                    *[
                        When(id=id, then=Value(order + 1))
                        for order, id in enumerate(new_full_order)
                    ],
                    default=Value(len(new_full_order) + 1),
                )
            }
        )

        return new_full_order


class FractionOrderableMixin(OrderableMixin):
    """
    This mixin introduces a set of helpers of the model is orderable by a decimal field.

    Needs a `models.DecimalField()` on the model.
    """

    @classmethod
    def get_highest_order_of_queryset(
        cls, queryset: QuerySet, amount: int = 1, field: str = "order"
    ) -> List[Decimal]:
        """
        Returns the highest existing values of the provided order field.

        :param queryset: The queryset containing the field to check.
        :param amount: The amount of order to return.
        :param field: The field name containing the value.
        :return: A list of highest order value in the queryset.
        """

        return get_highest_order_of_queryset(queryset, amount=amount, field=field)

    @classmethod
    def get_unique_orders_before_item(
        cls,
        before: Optional[models.Model],
        queryset: QuerySet,
        amount: int = 1,
        field: str = "order",
    ) -> List[Decimal]:
        """
        Calculates a list of unique decimal orders that can safely be used before the
        provided `before` item.

        :param before: The model instance where the before orders must be
            calculated for.
        :param queryset: The base queryset used to compute the value.
        :param amount: The number of orders that must be requested. Can be higher if
            multiple items are inserted or moved.
        :param field: The order field name.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the items must be recalculated in this
            case before calling this method again.
        :return: A list of decimals containing safe to use orders in order.
        """

        return get_unique_orders_before_item(before, queryset, amount, field=field)

    @classmethod
    def recalculate_full_orders(
        cls,
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

        return recalculate_full_orders(cls, field=field, queryset=queryset)


class PolymorphicContentTypeMixin:
    """
    This mixin introduces a set of helpers for a model that has a polymorphic
    relationship with django's content type. Note that a foreignKey to the ContentType
    model must exist.

    Example:
        content_type = models.ForeignKey(
            ContentType,
            verbose_name='content type',
            related_name='applications',
            on_delete=models.SET(get_default_application_content_type)
        )
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not hasattr(self.__class__, "content_type"):
            raise AttributeError(
                f"The attribute content_type doesn't exist on "
                f"{self.__class__.__name__}, but is required for the "
                f"PolymorphicContentTypeMixin."
            )

        if len(self.parent_ptrs()) > 1:
            raise AttributeError(
                f"The model "
                f"{self.__class__.__name__}, has multiple model parents, however "
                f"PolymorphicContentTypeMixin only allows a single parent and does "
                f"not support multiple inheritance."
            )

    def save(self, *args, **kwargs):
        self._ensure_content_type_is_set()
        super().save(*args, **kwargs)

    def _ensure_content_type_is_set(self):
        if not self.id:
            if not self.content_type_id:
                self.content_type = ContentType.objects.get_for_model(self)

    @cached_property
    def specific(self):
        """Returns this instance in its most specific subclassed form."""

        return self.get_specific()

    def get_specific(self, enhance_queryset: Callable = None):
        """
        Returns this instance in its most specific subclassed form.

        :param enhance_queryset: Allow to enhance the queryset before querying the
          specific instance.
        """

        self._ensure_content_type_is_set()
        model_class = self.specific_class
        if model_class is None:
            return self
        elif isinstance(self, model_class):
            return self
        else:
            content_type = ContentType.objects.get_for_id(self.content_type_id)
            # We deliberately want to use the `_base_manager` here so it's works exactly
            # so that trashed objects will still be fetched.
            queryset = content_type.model_class()._base_manager
            if callable(enhance_queryset):
                queryset = enhance_queryset(queryset)
            return queryset.get(id=self.id)

    @cached_property
    def specific_class(self):
        """
        Return the class that this application would be if instantiated in its
        most specific form.
        """

        self._ensure_content_type_is_set()
        content_type = ContentType.objects.get_for_id(self.content_type_id)
        return content_type.model_class()

    def parent_ptrs(self):
        model = self.__class__
        concrete_model = model._meta.concrete_model
        return [p for p in concrete_model._meta.parents.values() if p]

    def all_parents_and_self(self):
        parent_ptrs = self.parent_ptrs()
        if len(parent_ptrs) == 0:
            return [self]
        elif len(parent_ptrs) == 1:
            parent_name = parent_ptrs[0].name
            return [*getattr(self, parent_name).all_parents_and_self(), self]
        else:
            raise AttributeError(
                f"The model "
                f"{self.__class__.__name__}, has multiple model parents, however "
                f"PolymorphicContentTypeMixin only allows a single parent and does "
                f"not support multiple inheritance."
            )

    def change_polymorphic_type_to(self, new_model_class):
        """
        If you for example have two polymorphic types TypeA and TypeB which both have
        unique fields, an instance with TypeA can be changed to TypeB while keeping the
        parent values and id. This method actually changes the class and sets the
        default values in the __dict__.

        :param new_model_class: The new model class that the instance must be converted
            to.
        :type new_model_class: Model
        """

        old_fields = set([f for f in self._meta.get_fields()])
        new_fields = set([f for f in new_model_class._meta.get_fields()])
        field_names_to_remove = old_fields - new_fields
        field_names_to_add = new_fields - old_fields

        all_parents_and_self = self.all_parents_and_self()
        if len(all_parents_and_self) > 1:
            # Delete ourself and all of our parents upto the root parent. We can't just
            # delete the parent second from the top and rely on it cascading down
            # to all of the children due to a bug in Django which does not also pass
            # keep_parents=True to the children. This would result in all of the things
            # that CASCADE off the root parent itself being deleted if we didn't do it
            # this way.
            for parent_or_self in reversed(all_parents_and_self[1:]):
                parent_or_self.delete(keep_parents=True)
        self.__class__ = new_model_class
        self.content_type = ContentType.objects.get_for_model(new_model_class)

        def get_field_name(field):
            if isinstance(field, models.ForeignKey):
                return f"{field.name}_id"
            return field.name

        for field in field_names_to_remove:
            name = get_field_name(field)
            if name in self.__dict__:
                del self.__dict__[name]

            if isinstance(field, FieldCacheMixin) and field.is_cached(self):
                field.delete_cached_value(self)

        for field in field_names_to_add:
            name = get_field_name(field)
            field = new_model_class._meta.get_field(name)

            if isinstance(field, FieldCacheMixin) and field.is_cached(self):
                field.delete_cached_value(self)

            if hasattr(field, "default"):
                self.__dict__[name] = (
                    field.default if field.default != NOT_PROVIDED else None
                )

        # Because the field type has changed we need to invalidate the cached
        # properties so that they wont return the values of the old type.
        del self.specific
        del self.specific_class


T = TypeVar("T", bound="Instance")


class WithRegistry(Generic[T]):
    """
    Add shortcuts to models related to a registry.
    """

    @staticmethod
    @abc.abstractmethod
    def get_type_registry() -> ModelRegistryMixin:
        """Must return the registry related to this model class."""

    def get_type(self) -> T:
        """Returns the type for this model instance"""

        return self.get_type_registry().get_by_model(self.specific_class)


class BigAutoFieldMixin(models.Model):
    """
    This mixin introduces a BigAutoField as the primary key for the model.
    It is useful for models that require a large number of unique IDs.
    """

    id = models.BigAutoField(
        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
    )

    class Meta:
        abstract = True


class CreatedAndUpdatedOnMixin(models.Model):
    """
    This mixin introduces two new fields that store the created on and updated on
    timestamps.
    """

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = SyncedDateTimeField(sync_with_add="created_on", auto_now=True)

    class Meta:
        abstract = True


class AbstractModelMeta(abc.ABCMeta, type(models.Model)):
    pass


class HierarchicalModelMixin(models.Model, metaclass=AbstractModelMeta):
    """
    This mixin introduce some helpers for working with hierarchical models.
    """

    @classmethod
    @abc.abstractmethod
    def get_parent(self):
        """
        :return: The parent of this model. Returns None if this is the root.
        """

    def get_root(self):
        """
        :return: The root of the hierarchy.
        """

        root = self
        while r := root.get_parent():
            root = r
        return root

    class Meta:
        abstract = True


def make_trashable_mixin(parent):
    """
    Constructs a mixin class which overrides a models managers to ensure trashed entries
    are not available via objects, but instead via the new trash manager.

    :param parent: If specified will use the trashed column in a related model where
        parent is the name of the FK to the related model.
    :return: A mixin with overridden managers which correctly filter out trashed rows.
    """

    no_trash_manager = make_trash_manager(trashed=False, parent=parent)
    trash_only_manager = make_trash_manager(trashed=True, parent=parent)

    class TrashableMixin(models.Model):
        objects = no_trash_manager()
        trash = trash_only_manager()
        objects_and_trash = CTEManager()

        class Meta:
            abstract = True

    return TrashableMixin


ParentWorkspaceTrashableModelMixin = make_trashable_mixin("workspace")


class TrashableModelMixin(models.Model):
    """
    This mixin allows this model to be trashed and restored from the trash by adding
    new columns recording its trash status.
    """

    trashed = models.BooleanField(default=False, db_index=True)

    objects = NoTrashManager()
    trash = TrashOnlyManager()
    objects_and_trash = CTEManager()

    class Meta:
        abstract = True
