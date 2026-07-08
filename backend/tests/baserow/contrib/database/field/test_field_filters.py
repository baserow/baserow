from typing import List
from uuid import uuid4

from django.db.models import Q
from django.db.models.functions import Reverse, Upper

import pytest

from baserow.contrib.database.fields.field_filters import (
    FILTER_TYPE_AND,
    FILTER_TYPE_OR,
    AdvancedFilterBuilder,
    AnnotatedQ,
    FilterBuilder,
    GroupedFiltersAdapter,
)


@pytest.mark.django_db
def test_building_filter_with_and_type_ands_all_provided_qs_together(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=1, name="name")
    bool_field = data_fixture.create_boolean_field(
        table=table, order=2, name="is_active"
    )

    model = table.get_model()
    row_1 = model.objects.create(
        **{f"field_{text_field.id}": "name", f"field_{bool_field.id}": True}
    )
    model.objects.create(
        **{f"field_{text_field.id}": "name", f"field_{bool_field.id}": False}
    )

    builder = FilterBuilder(filter_type=FILTER_TYPE_AND)
    builder.filter(Q(**{f"field_{text_field.id}": "name"}))
    builder.filter(Q(**{f"field_{bool_field.id}": True}))

    queryset = builder.apply_to_queryset(model.objects)
    assert queryset.count() == 1
    assert row_1 in queryset


@pytest.mark.django_db
def test_building_filter_with_or_type_ors_all_provided_qs_together(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=1, name="name")
    another_text_field = data_fixture.create_text_field(
        table=table, order=2, name="surname"
    )

    model = table.get_model()
    row_1 = model.objects.create(
        **{f"field_{text_field.id}": "name", f"field_{another_text_field.id}": "other"}
    )
    row_2 = model.objects.create(
        **{
            f"field_{text_field.id}": "not_name",
            f"field_{another_text_field.id}": "extra",
        }
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "not_name",
            f"field_{another_text_field.id}": "not_other",
        }
    )

    builder = FilterBuilder(filter_type=FILTER_TYPE_OR)
    builder.filter(Q(**{f"field_{text_field.id}": "name"}))
    builder.filter(Q(**{f"field_{another_text_field.id}": "extra"}))

    queryset = builder.apply_to_queryset(model.objects)
    assert queryset.count() == 2
    assert row_1 in queryset
    assert row_2 in queryset


@pytest.mark.django_db
def test_building_filter_with_annotated_qs_annotates_prior_to_filter(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=1, name="name")
    another_text_field = data_fixture.create_text_field(
        table=table, order=2, name="surname"
    )

    model = table.get_model()
    row_1 = model.objects.create(
        **{f"field_{text_field.id}": "name", f"field_{another_text_field.id}": "other"}
    )
    model.objects.create(
        **{f"field_{text_field.id}": "eman", f"field_{another_text_field.id}": "extra"}
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "not_name",
            f"field_{another_text_field.id}": "not_other",
        }
    )

    builder = FilterBuilder(filter_type=FILTER_TYPE_OR)
    builder.filter(
        AnnotatedQ(
            annotation={"reversed_name": Reverse(f"field_{text_field.id}")},
            q={f"field_{text_field.id}": "name"},
        )
    )
    builder.filter(Q(**{f"reversed_name": "eman"}))

    queryset = builder.apply_to_queryset(model.objects)
    assert queryset.count() == 1
    assert row_1 in queryset


@pytest.mark.django_db
def test_building_filter_with_many_annotated_qs_merges_the_annotations(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=1, name="name")
    another_text_field = data_fixture.create_text_field(
        table=table, order=2, name="surname"
    )

    model = table.get_model()
    row_1 = model.objects.create(
        **{f"field_{text_field.id}": "name", f"field_{another_text_field.id}": "other"}
    )
    model.objects.create(
        **{f"field_{text_field.id}": "eman", f"field_{another_text_field.id}": "extra"}
    )
    model.objects.create(
        **{
            f"field_{text_field.id}": "not_name",
            f"field_{another_text_field.id}": "not_other",
        }
    )

    builder = FilterBuilder(filter_type=FILTER_TYPE_AND)
    builder.filter(
        AnnotatedQ(
            annotation={"reversed_name": Reverse(f"field_{text_field.id}")},
            q={f"field_{text_field.id}": "name"},
        )
    )
    builder.filter(
        AnnotatedQ(
            annotation={"upper_name": Upper(f"field_{text_field.id}")},
            q={f"field_{text_field.id}": "name"},
        )
    )
    builder.filter(Q(reversed_name="eman"))
    builder.filter(Q(upper_name="NAME"))

    queryset = builder.apply_to_queryset(model.objects)
    assert queryset.count() == 1
    assert row_1 in queryset


@pytest.mark.django_db
def test_can_invert_an_annotated_q(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text_field = data_fixture.create_text_field(table=table, order=1, name="name")
    another_text_field = data_fixture.create_text_field(
        table=table, order=2, name="surname"
    )

    model = table.get_model()
    model.objects.create(
        **{f"field_{text_field.id}": "name", f"field_{another_text_field.id}": "other"}
    )
    row_2 = model.objects.create(
        **{f"field_{text_field.id}": "eman", f"field_{another_text_field.id}": "extra"}
    )
    row_3 = model.objects.create(
        **{
            f"field_{text_field.id}": "not_name",
            f"field_{another_text_field.id}": "not_other",
        }
    )

    builder = FilterBuilder(filter_type=FILTER_TYPE_AND)
    q_to_invert = AnnotatedQ(
        annotation={"reversed_name": Reverse(f"field_{text_field.id}")},
        q={f"reversed_name": "eman"},
    )
    builder.filter(~q_to_invert)

    queryset = builder.apply_to_queryset(model.objects)
    assert queryset.count() == 2
    assert row_2 in queryset
    assert row_3 in queryset


class FakeViewFilter:
    def __init__(self, field_id, type, value, group_id, pk=None):
        self.pk = pk or uuid4()
        self.field_id = field_id
        self.type = type
        self.value = value
        self.group_id = group_id

    @property
    def id(self):
        return self.pk


class FakeViewFilterGroup:
    def __init__(self, filter_type, parent_group_id, pk=None):
        self.pk = pk or uuid4()
        self.filter_type = filter_type
        self.parent_group_id = parent_group_id

    @property
    def id(self):
        return self.pk


class FakeGroupedFiltersAdapter(GroupedFiltersAdapter):
    def __init__(
        self,
        filter_type: str,
        filters: List[FakeViewFilter],
        groups: List[FakeViewFilterGroup],
        model,
    ):
        self._filter_type = filter_type
        self._filters = filters
        self._groups = groups
        self.model = model

    @property
    def filter_type(self):
        return self._filter_type

    @property
    def filters(self):
        return self._filters

    @property
    def groups(self):
        return self._groups

    def get_q_from_filter(self, _filter):
        return Q(**{f"field_{_filter.field_id}__{_filter.type}": _filter.value})


@pytest.mark.django_db
def test_advanced_filter_builder_apply_filters_correctly(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    name_field = data_fixture.create_text_field(table=table, order=1, name="name")
    surname_field = data_fixture.create_text_field(table=table, order=2, name="surname")

    model = table.get_model()
    row_1 = model.objects.create(
        **{f"field_{name_field.id}": "Alan", f"field_{surname_field.id}": "Turing"}
    )
    row_2 = model.objects.create(
        **{f"field_{name_field.id}": "John", f"field_{surname_field.id}": "Turing"}
    )
    row_3 = model.objects.create(
        **{f"field_{name_field.id}": "Ada", f"field_{surname_field.id}": "Lovelace"}
    )

    filter_group_1 = FakeViewFilterGroup(FILTER_TYPE_AND, None)

    filter_1_g1 = FakeViewFilter(
        field_id=name_field.id, type="contains", value="a", group_id=filter_group_1.id
    )
    filter_2_g1 = FakeViewFilter(
        field_id=surname_field.id,
        type="exact",
        value="Turing",
        group_id=filter_group_1.id,
    )
    filter_3 = FakeViewFilter(
        field_id=name_field.id, type="exact", value="Ada", group_id=None
    )
    adapter = FakeGroupedFiltersAdapter(
        filter_type=FILTER_TYPE_OR,
        filters=[filter_1_g1, filter_2_g1, filter_3],
        groups=[filter_group_1],
        model=model,
    )

    filter_builder = AdvancedFilterBuilder(adapter).construct_filter_builder()
    queryset = filter_builder.apply_to_queryset(model.objects)
    assert queryset.count() == 2
    assert row_1 in queryset
    assert row_3 in queryset


@pytest.mark.django_db
def test_apply_to_queryset_only_uses_distinct_when_joins_can_duplicate_rows(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    other_table = data_fixture.create_database_table(user=user, database=table.database)
    text_field = data_fixture.create_text_field(table=table, name="text")
    link_field = data_fixture.create_link_row_field(
        table=table, link_row_table=other_table, name="link"
    )
    model = table.get_model()

    # A filter on a plain column can't duplicate rows, so no distinct is
    # needed, which keeps the count query a plain COUNT(*).
    scalar_queryset = FilterBuilder(FILTER_TYPE_AND).filter(
        Q(**{f"field_{text_field.id}": "a"})
    ).apply_to_queryset(model.objects.all())
    assert scalar_queryset.query.distinct is False

    # A filter joining through a link row relation can match the same row via
    # multiple join paths, so distinct must be kept.
    joined_queryset = FilterBuilder(FILTER_TYPE_AND).filter(
        Q(**{f"field_{link_field.id}__id__in": [1]})
    ).apply_to_queryset(model.objects.all())
    assert joined_queryset.query.distinct is True
