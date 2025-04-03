import pytest

from baserow.contrib.database.fields.dependencies.circular_reference_checker import (
    get_all_field_dependencies,
)
from baserow.contrib.database.fields.dependencies.exceptions import (
    CircularFieldDependencyError,
)
from baserow.contrib.database.fields.dependencies.handler import FieldDependencyHandler
from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.trash.handler import TrashHandler


def _unwrap_ids(qs):
    return list(qs.values_list("id", flat=True))


@pytest.mark.django_db
def test_formula_fields_will_be_rebuilt_to_depend_on_each_other(
    api_client, data_fixture, django_assert_num_queries
):
    first_formula_field = data_fixture.create_formula_field(
        name="first", formula_type="text", formula='"a"', setup_dependencies=False
    )
    dependant_formula = data_fixture.create_formula_field(
        name="second",
        table=first_formula_field.table,
        formula_type="text",
        formula="field('first')",
        setup_dependencies=False,
    )

    cache = FieldCache()
    FieldDependencyHandler.rebuild_dependencies([dependant_formula], cache)

    assert _unwrap_ids(dependant_formula.field_dependencies) == [first_formula_field.id]
    assert _unwrap_ids(dependant_formula.dependant_fields) == []

    assert _unwrap_ids(first_formula_field.field_dependencies) == []
    assert _unwrap_ids(first_formula_field.dependant_fields) == [dependant_formula.id]

    _assert_rebuilding_changes_nothing(cache, dependant_formula)


def _assert_rebuilding_changes_nothing(cache, field_to_rebuild):
    before_ids = list(
        FieldDependency.objects.order_by("id").values_list("id", flat=True)
    )
    before_strs = [str(f) for f in FieldDependency.objects.order_by("id").all()]
    # Rebuilding a second time doesn't change any field dependency rows
    FieldDependencyHandler.rebuild_dependencies([field_to_rebuild], cache)
    after_ids = list(
        FieldDependency.objects.order_by("id").values_list("id", flat=True)
    )
    after_strs = [str(f) for f in FieldDependency.objects.order_by("id").all()]
    assert before_ids == after_ids
    assert before_strs == after_strs


@pytest.mark.django_db
def test_rebuilding_with_a_circular_ref_will_raise(
    api_client, data_fixture, django_assert_num_queries
):
    first_formula_field = data_fixture.create_formula_field(
        name="first",
        formula_type="text",
        formula='field("second")',
        setup_dependencies=False,
    )
    second_formula_field = data_fixture.create_formula_field(
        name="second",
        table=first_formula_field.table,
        formula_type="text",
        formula="field('first')",
        setup_dependencies=False,
    )

    cache = FieldCache()
    FieldDependencyHandler.rebuild_dependencies([first_formula_field], cache)
    with pytest.raises(CircularFieldDependencyError):
        FieldDependencyHandler.rebuild_dependencies([second_formula_field], cache)

    assert _unwrap_ids(second_formula_field.field_dependencies) == []
    assert _unwrap_ids(second_formula_field.dependant_fields) == [
        first_formula_field.id
    ]

    assert _unwrap_ids(first_formula_field.field_dependencies) == [
        second_formula_field.id
    ]
    assert _unwrap_ids(first_formula_field.dependant_fields) == []


@pytest.mark.django_db
def test_rebuilding_a_link_row_field_creates_dependencies_with_vias(
    api_client, data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    other_table = data_fixture.create_database_table()
    data_fixture.create_text_field(primary=True, name="primary", table=table)
    other_primary_field = data_fixture.create_text_field(
        primary=True, name="primary", table=other_table
    )
    link_row_field = data_fixture.create_link_row_field(
        name="link", table=table, link_row_table=other_table
    )

    cache = FieldCache()
    FieldDependencyHandler.rebuild_dependencies([link_row_field], cache)

    assert _unwrap_ids(link_row_field.field_dependencies) == [other_primary_field.id]
    assert _unwrap_ids(link_row_field.dependant_fields) == []
    assert link_row_field.vias.count() == 1
    via = link_row_field.vias.get()
    assert via.dependency.id == other_primary_field.id
    assert via.dependant.id == link_row_field.id
    assert via.via.id == link_row_field.id

    _assert_rebuilding_changes_nothing(cache, link_row_field)


@pytest.mark.django_db
def test_trashing_a_link_row_field_breaks_vias(
    api_client, data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    other_table = data_fixture.create_database_table()
    data_fixture.create_text_field(primary=True, name="primary", table=table)
    field = data_fixture.create_text_field(name="field", table=table)
    other_primary_field = data_fixture.create_text_field(
        primary=True, name="primary", table=other_table
    )
    link_row_field = data_fixture.create_link_row_field(
        name="link", table=table, link_row_table=other_table
    )

    cache = FieldCache()
    FieldDependencyHandler.rebuild_dependencies([link_row_field], cache)

    # Create a fake dependencies until we have lookup fields
    via_dep = FieldDependency.objects.create(
        dependency=other_primary_field, via=link_row_field, dependant=field
    )
    direct_dep = FieldDependency.objects.create(
        dependency=link_row_field, dependant=field
    )

    link_row_field.trashed = True
    link_row_field.save()
    FieldDependencyHandler.break_dependencies_delete_dependants(link_row_field)

    # The trashed field is no longer part of the graph
    assert not link_row_field.dependencies.exists()
    assert not link_row_field.vias.exists()
    assert not link_row_field.dependants.exists()

    # The dep that went via the trashed field has been deleted
    assert not FieldDependency.objects.filter(id=via_dep.id).exists()

    direct_dep.refresh_from_db()
    assert direct_dep.dependency is None
    assert direct_dep.broken_reference_field_name == "link"
    assert direct_dep.via is None


@pytest.mark.django_db
def test_trashing_a_lookup_target_still_has_the_dep_depend_on_the_through_field(
    data_fixture,
):
    table = data_fixture.create_database_table()
    other_table = data_fixture.create_database_table()
    data_fixture.create_text_field(primary=True, name="primary", table=table)
    data_fixture.create_text_field(name="field", table=table)
    data_fixture.create_text_field(primary=True, name="primary", table=other_table)
    target_field = data_fixture.create_text_field(name="target", table=other_table)
    link_row_field = data_fixture.create_link_row_field(
        name="link", table=table, link_row_table=other_table
    )
    lookup_field = data_fixture.create_lookup_field(
        table=table,
        through_field=link_row_field,
        target_field=target_field,
        through_field_name=link_row_field.name,
        target_field_name=target_field.name,
        setup_dependencies=False,
    )

    cache = FieldCache()
    FieldDependencyHandler.rebuild_dependencies([link_row_field], cache)
    FieldDependencyHandler.rebuild_dependencies([lookup_field], cache)

    target_field.trashed = True
    target_field.save()

    assert target_field.dependants.exists()
    assert link_row_field.dependencies.count() == 1
    assert lookup_field.dependencies.count() == 1

    FieldDependencyHandler.break_dependencies_delete_dependants(target_field)

    # The trashed field is no longer part of the graph
    assert not target_field.dependants.exists()
    assert link_row_field.dependencies.count() == 1
    assert lookup_field.dependencies.count() == 1

    assert FieldDependency.objects.filter(via=link_row_field).count() == 2
    assert FieldDependency.objects.filter(
        broken_reference_field_name=target_field.name,
        dependency__isnull=True,
        via=link_row_field,
        dependant=lookup_field,
    ).get()


@pytest.mark.django_db
def test_str_of_field_dependency_uniquely_identifies_it(
    api_client, data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    table_b = data_fixture.create_database_table()
    field_a = data_fixture.create_text_field(primary=True, name="a", table=table)
    field_b = data_fixture.create_text_field(name="b", table=table)

    via_field = data_fixture.create_link_row_field(
        name="via", table=table, link_row_table=table_b
    )
    other_via_field = data_fixture.create_link_row_field(
        name="other_via", table=table, link_row_table=table_b
    )
    first_a_to_b = FieldDependency(dependant=field_a, dependency=field_b)
    second_a_to_b = FieldDependency(dependant=field_a, dependency=field_b)
    with django_assert_num_queries(0):
        assert str(first_a_to_b) == str(second_a_to_b)
    # Saving so they have id's should still return the same strings even though they
    # have different ids now
    first_a_to_b.save()
    second_a_to_b.save()
    assert first_a_to_b.id != second_a_to_b.id
    with django_assert_num_queries(0):
        assert str(first_a_to_b) == str(second_a_to_b)

        assert str(FieldDependency(dependant=field_a, dependency=field_b)) != str(
            FieldDependency(dependant=field_b, dependency=field_a)
        )

        # If all the same with a via field
        assert str(
            FieldDependency(dependant=field_a, via=via_field, dependency=field_b)
        ) == str(FieldDependency(dependant=field_a, via=via_field, dependency=field_b))
        # If one doesn't have a via
        assert str(
            FieldDependency(dependant=field_a, via=via_field, dependency=field_b)
        ) != str(FieldDependency(dependant=field_a, dependency=field_b))
        # If the vias differ then
        assert str(
            FieldDependency(dependant=field_a, via=via_field, dependency=field_b)
        ) != str(
            FieldDependency(dependant=field_a, via=other_via_field, dependency=field_b)
        )

        # Normal broken refs
        assert str(
            FieldDependency(dependant=field_a, broken_reference_field_name="b")
        ) == str(FieldDependency(dependant=field_a, broken_reference_field_name="b"))
        # Different broken ref
        assert str(
            FieldDependency(dependant=field_a, broken_reference_field_name="b")
        ) != str(FieldDependency(dependant=field_a, broken_reference_field_name="c"))
        # Different dependant
        assert str(
            FieldDependency(dependant=field_a, broken_reference_field_name="b")
        ) != str(FieldDependency(dependant=field_b, broken_reference_field_name="b"))

        # Via broken refs
        assert str(
            FieldDependency(
                dependant=field_a, via=via_field, broken_reference_field_name="via"
            )
        ) == str(
            FieldDependency(
                dependant=field_a,
                via=via_field,
                broken_reference_field_name="via",
            )
        )
        # Different via same broken
        assert str(
            FieldDependency(
                dependant=field_a, via=via_field, broken_reference_field_name="via"
            )
        ) != str(
            FieldDependency(
                dependant=field_a,
                via=other_via_field,
                broken_reference_field_name="via",
            )
        )
        # Same via different broken
        assert str(
            FieldDependency(
                dependant=field_a, via=via_field, broken_reference_field_name="via"
            )
        ) != str(
            FieldDependency(
                dependant=field_a,
                via=via_field,
                broken_reference_field_name="other",
            )
        )
        # Same via same broken different dependant
        assert str(
            FieldDependency(
                dependant=field_a, via=via_field, broken_reference_field_name="via"
            )
        ) != str(
            FieldDependency(
                dependant=field_b,
                via=via_field,
                broken_reference_field_name="via",
            )
        )


@pytest.mark.django_db
def test_trashing_and_restoring_a_field_recreate_dependencies_correctly(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    text = data_fixture.create_text_field(name="text", table=table)
    f1 = data_fixture.create_formula_field(
        name="f1", table=table, formula_type="text", formula="field('text')"
    )
    f1_id = f1.id
    f2 = data_fixture.create_formula_field(
        name="f2", table=table, formula_type="text", formula="field('f1')"
    )

    field_cache = FieldCache()
    deps = FieldDependencyHandler.group_all_dependent_fields_by_level(
        table.id, [text.id], field_cache, associated_relations_changed=False
    )
    assert len(deps) == 2
    assert deps[0][0][0] == f1
    assert deps[1][0][0] == f2

    row_1 = RowHandler().force_create_row(user, table, {text.db_column: "a"})
    assert getattr(row_1, f2.db_column) == "a"

    FieldHandler().delete_field(user, f1)
    deps = FieldDependencyHandler.group_all_dependent_fields_by_level(
        table.id, [text.id], field_cache, associated_relations_changed=False
    )
    assert len(deps) == 0
    FieldDependency.objects.get(dependant=f2).broken_reference_field_name == "f1"

    # Adding a new row should not update the f2 field since the f1 field is missing
    row_2 = RowHandler().force_create_row(user, table, {text.db_column: "b"})
    assert getattr(row_2, f2.db_column) is None

    # restoring the f1 field should fix the f2 field and row values
    TrashHandler().restore_item(user, "field", f1_id)
    deps = FieldDependencyHandler.group_all_dependent_fields_by_level(
        table.id, [text.id], field_cache, associated_relations_changed=False
    )
    assert len(deps) == 2
    assert deps[0][0][0] == f1
    assert deps[1][0][0] == f2

    row_2.refresh_from_db()
    assert getattr(row_2, f1.db_column) == "b"
    assert getattr(row_2, f2.db_column) == "b"


@pytest.mark.django_db
def test_even_with_circular_dependencies_queries_finish_in_time(data_fixture):
    # This should never happen, but if somehow circular dependencies are created
    # we should still be able to get the dependencies of a field without running
    # into an infinite loop in the recursive query.

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    f1 = data_fixture.create_formula_field(
        name="f1", table=table, formula_type="text", formula="1"
    )
    f2 = data_fixture.create_formula_field(
        name="f2", table=table, formula_type="text", formula="field('f1')"
    )
    # Forcefully create a circular dependency
    f1.dependencies.create(dependency=f2)

    with pytest.raises(CircularFieldDependencyError):
        assert get_all_field_dependencies(f1) == {f2.id}  # f1 -> f2

    with pytest.raises(CircularFieldDependencyError):
        assert get_all_field_dependencies(f2) == {f1.id}  # f2 -> f1
