from collections import defaultdict
from typing import Optional, Type

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Model


class FieldCache:
    """
    A cache which can be used to get the specific version of a field given a
    non-specific version or to get a field using a table and field name. If a cache
    miss occurs it will actually lookup the field from the database, cache it and
    return it, otherwise if the field does not exist None will be returned.

    Trashed fields are excluded from the cache.
    """

    def __init__(
        self,
        existing_cache: Optional["FieldCache"] = None,
        existing_model: Optional[Type[Model]] = None,
    ):
        if existing_cache is not None:
            self._cached_field_by_name_per_table = (
                existing_cache._cached_field_by_name_per_table
            )
            self._model_cache = existing_cache._model_cache
        else:
            self._cached_field_by_name_per_table = defaultdict(dict)
            self._model_cache = {}

        if existing_model is not None:
            self.cache_model(existing_model)

    # noinspection PyUnresolvedReferences,PyProtectedMember
    def cache_model(self, model: Type[Model]):
        self._model_cache[model.baserow_table_id] = model
        self.cache_model_fields(model)

    # noinspection PyUnresolvedReferences,PyProtectedMember
    def cache_model_fields(self, model: Type[Model]):
        for field_object in model._field_objects.values():
            self.cache_field(field_object["field"])

    def get_model(self, table):
        table_id = table.id
        if table_id not in self._model_cache:
            model = table.get_model()
            self._model_cache[table_id] = model
            # Immediately cache the model fields because they're already in the most
            # specific form, and they might be needed later. This reduces the number
            # of queries.
            self.cache_model_fields(model)
        return self._model_cache[table_id]

    def uncache_field(self, field):
        return self._cached_field_by_name_per_table[field.table_id].pop(
            field.name, None
        )

    def reset_cache(self):
        self._cached_field_by_name_per_table = defaultdict(dict)
        self._model_cache = {}

    def cache_field(self, field):
        if not field.trashed:
            cached_fields = self._cached_field_by_name_per_table[field.table_id]

            try:
                specific_field = field.specific
            except ObjectDoesNotExist:
                return None

            cached_fields[field.name] = specific_field
            return specific_field
        else:
            return None

    def lookup_specific(self, non_specific_field, fetch_if_missing=True):
        try:
            return self._cached_field_by_name_per_table[non_specific_field.table_id][
                non_specific_field.name
            ]
        except KeyError:
            if fetch_if_missing:
                return self.cache_field(non_specific_field)
            else:
                return None

    def lookup_by_name(self, table, field_name: str):
        try:
            return self._cached_field_by_name_per_table[table.id][field_name]
        except KeyError:
            try:
                return self.cache_field(table.field_set.get(name=field_name))
            except ObjectDoesNotExist:
                return None
