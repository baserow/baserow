from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings

import pytest
from pytest_unordered import unordered

from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.dependencies.exceptions import (
    CircularFieldDependencyError,
    SelfReferenceFieldDependencyError,
)
from baserow.contrib.database.fields.dependencies.handler import FieldDependencyHandler
from baserow.contrib.database.fields.dependencies.models import FieldDependency
from baserow.contrib.database.fields.field_cache import FieldCache
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import LinkRowField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.core.registries import ImportExportConfig


@pytest.mark.django_db
def test_get_same_table_deps(data_fixture):
    field_a = data_fixture.create_text_field()
    field_b = data_fixture.create_text_field(table=field_a.table)
    field_c = data_fixture.create_text_field(table=field_a.table)
    field_in_other_table = data_fixture.create_text_field()
    FieldDependency.objects.create(dependant=field_a, dependency=field_b)
    FieldDependency.objects.create(dependant=field_b, dependency=field_c)
    FieldDependency.objects.create(dependant=field_c, dependency=field_in_other_table)
    assert FieldDependencyHandler().get_same_table_dependencies(field_a) == [field_b]
    assert FieldDependencyHandler().get_same_table_dependencies(field_b) == [field_c]
    assert FieldDependencyHandler().get_same_table_dependencies(field_c) == []


def when_field_updated(field, via=None, relation_changed=True):
    result = []
    for (
        dependant_field,
        dependant_field_type,
        via_path_to_starting_table,
    ) in field.dependant_fields_with_types(
        field_cache=FieldCache(),
        starting_via_path_to_starting_table=via,
        associated_relation_changed=relation_changed,
    ):
        if via_path_to_starting_table is None:
            via_path_to_starting_table = []
        result_dict = {
            "field": dependant_field,
            "via": via_path_to_starting_table,
        }
        then = when_field_updated(
            dependant_field, via=via_path_to_starting_table, relation_changed=False
        )
        if then:
            result_dict["then"] = then
        result.append(result_dict)
    return result


@pytest.mark.django_db
def test_dependencies_for_primary_lookup(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, table_a_link_field = data_fixture.create_two_linked_tables(
        user=user
    )

    table_a_primary = table_a.field_set.get(primary=True)
    table_b_link_field = table_a_link_field.link_row_related_field

    table_b_primary = table_b.field_set.get(primary=True)
    FieldHandler().update_field(
        user,
        table_a_primary.specific,
        new_type_name="formula",
        formula=f"lookup('{table_a_link_field.name}', '{table_b_primary.name}')",
    )

    assert when_field_updated(table_b_primary) == causes(
        a_field_update_for(table_a_link_field, via=[table_a_link_field]),
        a_field_update_for(
            table_a_primary.specific,
            via=[table_a_link_field],
            then=causes(
                a_field_update_for(
                    table_b_link_field,
                    via=[table_a_link_field, table_b_link_field],
                )
            ),
        ),
    )
    assert when_field_updated(table_a_primary) == causes(
        a_field_update_for(table_b_link_field, via=[table_b_link_field]),
    )
    assert when_field_updated(table_b_link_field) == causes(
        a_field_update_for(table_a_link_field, via=[table_a_link_field]),
        a_field_update_for(
            table_a_primary.specific,
            via=[table_a_link_field],
            then=causes(
                a_field_update_for(
                    table_b_link_field,
                    via=[table_a_link_field, table_b_link_field],
                )
            ),
        ),
    )

    assert when_field_updated(table_a_link_field) == causes(
        a_field_update_for(table_b_link_field, via=[table_b_link_field]),
        a_field_update_for(
            table_a_primary.specific,
            via=[],
            then=causes(
                a_field_update_for(
                    table_b_link_field,
                    via=[table_b_link_field],
                )
            ),
        ),
    )


@pytest.mark.django_db
def test_dependencies_for_triple_lookup(data_fixture):
    user = data_fixture.create_user()
    table_a, table_b, table_a_to_b_link_field = data_fixture.create_two_linked_tables(
        user=user
    )
    table_c, _, table_c_to_b_link_field = data_fixture.create_two_linked_tables(
        user=user, table_b=table_b
    )

    table_a_primary = table_a.field_set.get(primary=True).specific
    table_b_to_a_link_field = table_a_to_b_link_field.link_row_related_field
    table_b_to_c_link_field = table_c_to_b_link_field.link_row_related_field

    table_b_primary = table_b.field_set.get(primary=True).specific
    table_c_primary = table_c.field_set.get(primary=True).specific

    lookup_of_linked_field = FieldHandler().create_field(
        user,
        table=table_a,
        type_name="formula",
        name="lookup_of_link_field",
        formula=f"lookup('{table_a_to_b_link_field.name}', "
        f"'{table_b_to_c_link_field.name}')",
    )
    assert lookup_of_linked_field.error is None

    assert when_field_updated(table_c_primary) == causes(
        a_field_update_for(
            table_b_to_c_link_field,
            via=[table_b_to_c_link_field],
            then=causes(
                a_field_update_for(
                    lookup_of_linked_field,
                    via=[table_b_to_c_link_field, table_a_to_b_link_field],
                )
            ),
        )
    )
    assert when_field_updated(table_b_to_c_link_field) == causes(
        a_field_update_for(
            table_c_to_b_link_field,
            via=[table_c_to_b_link_field],
        ),
        a_field_update_for(
            lookup_of_linked_field,
            via=[table_a_to_b_link_field],
        ),
    )


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_dependencies_for_link_row_link_row_self_reference(data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user=user)
    table_a_primary = data_fixture.create_text_field(table=table_a, primary=True)

    table_a_self_link = FieldHandler().create_field(
        user,
        table=table_a,
        type_name="link_row",
        name="self",
        link_row_table=table_a,
    )
    assert when_field_updated(table_a_primary) == causes(
        a_field_update_for(field=table_a_self_link, via=[table_a_self_link])
    )


@pytest.mark.django_db
def test_self_reference_raises(data_fixture):
    user = data_fixture.create_user()
    table_a = data_fixture.create_database_table(user=user)

    with pytest.raises(SelfReferenceFieldDependencyError):
        FieldHandler().create_field(
            user,
            table=table_a,
            type_name="formula",
            name="self_ref",
            formula="field('self_ref')",
        )


def causes(*result):
    return list(result)


def a_field_update_for(field, via, then=None):
    r = {
        "field": field,
        "via": via,
    }
    if then:
        r["then"] = then
    return r


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_get_all_dependant_fields_with_type(data_fixture):
    table = data_fixture.create_database_table()
    text_field_1 = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)

    text_field_1_dependency_1 = data_fixture.create_text_field(table=table)
    text_field_1_dependency_2 = data_fixture.create_text_field(table=table)

    text_field_2_dependency_1 = data_fixture.create_text_field(table=table)
    text_field_2_dependency_2 = data_fixture.create_text_field(table=table)
    text_field_2_dependency_3 = data_fixture.create_text_field(table=table)

    text_field_1_dependency_1_dependency_1 = data_fixture.create_text_field(table=table)
    text_field_1_dependency_2_dependency_1 = data_fixture.create_text_field(table=table)
    text_field_2_dependency_1_dependency_1 = data_fixture.create_text_field(table=table)

    link_field_to_table = data_fixture.create_link_row_field(link_row_table=table)
    text_field_1_and_2_dependency_1 = data_fixture.create_text_field(table=table)
    other_table_field = data_fixture.create_text_field(
        table=link_field_to_table.link_row_table
    )

    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_1
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_2
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_and_2_dependency_1
    )

    FieldDependency.objects.create(
        dependency=text_field_2, dependant=text_field_2_dependency_1
    )
    FieldDependency.objects.create(
        dependency=text_field_2,
        dependant=other_table_field,
        via=link_field_to_table,
    )
    FieldDependency.objects.create(
        dependency=text_field_2, dependant=text_field_2_dependency_3
    )
    FieldDependency.objects.create(
        dependency=text_field_2, dependant=text_field_1_and_2_dependency_1
    )

    FieldDependency.objects.create(
        dependency=text_field_1_dependency_1,
        dependant=text_field_1_dependency_1_dependency_1,
    )
    FieldDependency.objects.create(
        dependency=text_field_1_dependency_2,
        dependant=text_field_1_dependency_2_dependency_1,
    )
    FieldDependency.objects.create(
        dependency=text_field_2_dependency_1,
        dependant=text_field_2_dependency_1_dependency_1,
    )

    field_cache = FieldCache()
    text_field_type = field_type_registry.get_by_model(text_field_1_dependency_1)

    results = FieldDependencyHandler.get_all_dependent_fields_with_type(
        table.id,
        field_ids=[text_field_1.id],
        field_cache=field_cache,
        associated_relations_changed=True,
    )
    expected_text_field_1_dependants = [
        (text_field_1_dependency_1, text_field_type, None),
        (text_field_1_dependency_2, text_field_type, None),
        (text_field_1_and_2_dependency_1, text_field_type, None),
        (text_field_1_dependency_1_dependency_1, text_field_type, None),
        (text_field_1_dependency_2_dependency_1, text_field_type, None),
    ]
    assert results == unordered(expected_text_field_1_dependants)

    results = FieldDependencyHandler.get_all_dependent_fields_with_type(
        table.id,
        field_ids=[text_field_2.id],
        field_cache=field_cache,
        associated_relations_changed=True,
    )
    expected_text_field_2_dependants = [
        (text_field_2_dependency_1, text_field_type, None),
        (other_table_field, text_field_type, [link_field_to_table]),
        (text_field_2_dependency_3, text_field_type, None),
        (text_field_1_and_2_dependency_1, text_field_type, None),
        (text_field_2_dependency_1_dependency_1, text_field_type, None),
    ]
    assert results == unordered(expected_text_field_2_dependants)

    results = FieldDependencyHandler.get_all_dependent_fields_with_type(
        table.id,
        field_ids=[text_field_3.id],
        field_cache=field_cache,
        associated_relations_changed=True,
    )
    assert len(results) == 0

    results = FieldDependencyHandler.get_all_dependent_fields_with_type(
        table.id,
        field_ids=[text_field_1.id, text_field_2.id, text_field_3.id],
        field_cache=field_cache,
        associated_relations_changed=True,
    )
    expected_text_field_1_2_3_dependants = [
        # This is a combination of `expected_text_field_1_dependants` and
        # `expected_text_field_2_dependants`, but without the duplicates.
        (text_field_1_dependency_1, text_field_type, None),
        (text_field_1_dependency_2, text_field_type, None),
        (text_field_1_dependency_1_dependency_1, text_field_type, None),
        (text_field_1_dependency_2_dependency_1, text_field_type, None),
        (text_field_2_dependency_1, text_field_type, None),
        (other_table_field, text_field_type, [link_field_to_table]),
        (text_field_2_dependency_3, text_field_type, None),
        (text_field_1_and_2_dependency_1, text_field_type, None),
        (text_field_2_dependency_1_dependency_1, text_field_type, None),
    ]
    assert results == unordered(expected_text_field_1_2_3_dependants)

    results = FieldDependencyHandler.group_all_dependent_fields_by_level(
        table.id,
        field_ids=[text_field_1.id, text_field_2.id, text_field_3.id],
        field_cache=field_cache,
        associated_relations_changed=True,
    )
    expexted_results_by_depth = (
        [
            (text_field_1_dependency_1, text_field_type, None),
            (text_field_1_dependency_2, text_field_type, None),
            (text_field_2_dependency_1, text_field_type, None),
            (other_table_field, text_field_type, [link_field_to_table]),
            (text_field_2_dependency_3, text_field_type, None),
            (text_field_1_and_2_dependency_1, text_field_type, None),
        ],
        [
            (text_field_1_dependency_1_dependency_1, text_field_type, None),
            (text_field_1_dependency_2_dependency_1, text_field_type, None),
            (text_field_2_dependency_1_dependency_1, text_field_type, None),
        ],
    )

    for i, layer in enumerate(results):
        assert layer == unordered(expexted_results_by_depth[i])


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_get_all_dependant_fields_with_type_num_queries(
    data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    text_field_1 = data_fixture.create_text_field(table=table)

    text_field_1_dependency_1 = data_fixture.create_text_field(table=table)
    text_field_1_dependency_2 = data_fixture.create_number_field(table=table)
    text_field_1_and_2_dependency_1 = data_fixture.create_text_field(table=table)

    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_1
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_2
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_and_2_dependency_1
    )

    # This content type is fetched in the method, but it's also cached after.
    # Fetching it in the test, ensures that we see a correct number of queries after.
    ContentType.objects.get_for_model(LinkRowField)

    with django_assert_num_queries(3):
        FieldDependencyHandler.get_all_dependent_fields_with_type(
            table.id,
            field_ids=[text_field_1.id],
            field_cache=FieldCache(),
            associated_relations_changed=True,
        )

    text_field_1_dependency_3 = data_fixture.create_text_field(table=table)
    text_field_1_dependency_4 = data_fixture.create_number_field(table=table)
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_3
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_4
    )

    with django_assert_num_queries(3):
        FieldDependencyHandler.get_all_dependent_fields_with_type(
            table.id,
            field_ids=[text_field_1.id],
            field_cache=FieldCache(),
            associated_relations_changed=True,
        )


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_get_all_dependant_fields_with_type_via_field_num_queries(
    data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    table2 = data_fixture.create_database_table()
    text_field_1 = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table2)
    link_field_to_table = data_fixture.create_link_row_field(table=table)

    FieldDependency.objects.create(
        dependency=text_field_1,
        dependant=text_field_2,
        via=link_field_to_table,
    )

    with django_assert_num_queries(3):
        dependant_fields = FieldDependencyHandler.get_all_dependent_fields_with_type(
            table.id,
            field_ids=[text_field_1.id],
            field_cache=FieldCache(),
            associated_relations_changed=True,
        )

        (
            dependant_field,
            dependant_field_type,
            path_to_starting_table,
        ) = dependant_fields[0]
        str(dependant_field.table.id)
        str(path_to_starting_table[0].table.id)
        str(path_to_starting_table[0].link_row_table.id)


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_get_dependant_fields_with_type(data_fixture):
    table = data_fixture.create_database_table()
    text_field_1 = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    text_field_3 = data_fixture.create_text_field(table=table)

    text_field_1_dependency_1 = data_fixture.create_text_field(table=table)
    text_field_1_dependency_2 = data_fixture.create_text_field(table=table)

    text_field_2_dependency_1 = data_fixture.create_text_field(table=table)
    text_field_2_dependency_2 = data_fixture.create_text_field(table=table)
    text_field_2_dependency_3 = data_fixture.create_text_field(table=table)

    link_field_to_table = data_fixture.create_link_row_field(link_row_table=table)
    text_field_1_and_2_dependency_1 = data_fixture.create_text_field(table=table)
    other_table_field = data_fixture.create_text_field(
        table=link_field_to_table.link_row_table
    )

    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_1
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_2
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_and_2_dependency_1
    )

    FieldDependency.objects.create(
        dependency=text_field_2, dependant=text_field_2_dependency_1
    )
    FieldDependency.objects.create(
        dependency=text_field_2,
        dependant=other_table_field,
        via=link_field_to_table,
    )
    FieldDependency.objects.create(
        dependency=text_field_2, dependant=text_field_2_dependency_3
    )
    FieldDependency.objects.create(
        dependency=text_field_2, dependant=text_field_1_and_2_dependency_1
    )

    field_cache = FieldCache()
    text_field_type = field_type_registry.get_by_model(text_field_1_dependency_1)

    results = FieldDependencyHandler.get_dependant_fields_with_type(
        table.id,
        field_ids=[text_field_1.id],
        associated_relations_changed=True,
        field_cache=field_cache,
    )
    expected_text_field_1_dependants = [
        (text_field_1_dependency_1, text_field_type, None),
        (text_field_1_dependency_2, text_field_type, None),
        (text_field_1_and_2_dependency_1, text_field_type, None),
    ]
    assert results == unordered(expected_text_field_1_dependants)

    results = FieldDependencyHandler.get_dependant_fields_with_type(
        table.id,
        field_ids=[text_field_2.id],
        associated_relations_changed=True,
        field_cache=field_cache,
    )
    expected_text_field_2_dependants = [
        (text_field_2_dependency_1, text_field_type, None),
        (other_table_field, text_field_type, [link_field_to_table]),
        (
            text_field_2_dependency_3,
            text_field_type,
            None,
        ),
        (text_field_1_and_2_dependency_1, text_field_type, None),
    ]
    assert results == unordered(expected_text_field_2_dependants)

    results = FieldDependencyHandler.get_dependant_fields_with_type(
        table.id,
        field_ids=[text_field_3.id],
        associated_relations_changed=True,
        field_cache=field_cache,
    )
    assert len(results) == 0

    results = FieldDependencyHandler.get_dependant_fields_with_type(
        table.id,
        field_ids=[text_field_1.id, text_field_2.id, text_field_3.id],
        associated_relations_changed=True,
        field_cache=field_cache,
    )
    assert results == unordered(
        expected_text_field_1_dependants + expected_text_field_2_dependants
    )


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_get_dependant_fields_with_type_num_queries(
    data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    text_field_1 = data_fixture.create_text_field(table=table)

    text_field_1_dependency_1 = data_fixture.create_text_field(table=table)
    text_field_1_dependency_2 = data_fixture.create_number_field(table=table)
    text_field_1_and_2_dependency_1 = data_fixture.create_text_field(table=table)

    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_1
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_2
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_and_2_dependency_1
    )

    with django_assert_num_queries(3):
        FieldDependencyHandler.get_dependant_fields_with_type(
            table.id,
            field_ids=[text_field_1.id],
            associated_relations_changed=True,
            field_cache=FieldCache(),
        )

    text_field_1_dependency_3 = data_fixture.create_text_field(table=table)
    text_field_1_dependency_4 = data_fixture.create_number_field(table=table)
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_3
    )
    FieldDependency.objects.create(
        dependency=text_field_1, dependant=text_field_1_dependency_4
    )

    with django_assert_num_queries(3):
        FieldDependencyHandler.get_dependant_fields_with_type(
            table.id,
            field_ids=[text_field_1.id],
            associated_relations_changed=True,
            field_cache=FieldCache(),
        )


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_get_dependant_fields_with_type_via_field_num_queries(
    data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    text_field_1 = data_fixture.create_text_field(table=table)
    text_field_2 = data_fixture.create_text_field(table=table)
    link_field_to_table = data_fixture.create_link_row_field(table=table)

    FieldDependency.objects.create(
        dependency=text_field_1,
        dependant=text_field_2,
        via=link_field_to_table,
    )

    with django_assert_num_queries(2):
        dependant_fields = FieldDependencyHandler.get_dependant_fields_with_type(
            table.id,
            field_ids=[text_field_1.id],
            associated_relations_changed=True,
            field_cache=FieldCache(),
        )

        (
            dependant_field,
            dependant_field_type,
            path_to_starting_table,
        ) = dependant_fields[0]
        str(dependant_field.table.id)
        str(path_to_starting_table[0].table.id)
        str(path_to_starting_table[0].link_row_table.id)


@pytest.mark.django_db
def test_dependency_handler_group_dependencies_by_level(data_fixture):
    # fmt: off
    dependencies = dependencies = {
        'A': set(),      # No dependencies
        'B': {'A'},      # Depends on A
        'C': {'B'},      # Depends on B
        'D': {'B'},      # Depends on B
        'E': {'C', 'D'}  # Depends on C and D
    }
    # fmt: on

    levels = FieldDependencyHandler.group_dependencies_by_level(dependencies)

    # fmt: off
    assert list(levels) == [
        ['A'],
        ['B'],
        ['C', 'D'],
        ['E']
    ]
    # fmt: on


@pytest.mark.django_db
def test_dependency_handler_group_dependencies_by_level_circular_dep_error(
    data_fixture,
):
    # fmt: off
    dependencies = dependencies = {
        'A': {'B'},      # Depends on B
        'B': {'A'},      # Depends on A
    }
    # fmt: on

    with pytest.raises(CircularFieldDependencyError):
        FieldDependencyHandler.group_dependencies_by_level(dependencies)


EXPORTED_TABLES_WITH_DEPENDENCIES_EXAMPLE = [
    {
        "id": 600,
        "name": "t1",
        "order": 1,
        "fields": [
            {
                "id": 5736,
                "type": "text",
                "name": "name",
                "order": 0,
                "primary": True,
                "text_default": "",
            },
            {
                "id": 5737,
                "type": "formula",
                "name": "formula",
                "order": 1,
                "primary": False,
                "nullable": True,
                "formula": "field('text')",
                "formula_type": "text",
            },
            {
                "id": 5738,
                "type": "text",
                "name": "text",
                "order": 2,
                "primary": False,
                "text_default": "",
            },
            {
                "id": 5742,
                "type": "link_row",
                "name": "t2",
                "order": 3,
                "primary": False,
                "link_row_table_id": 601,
                "link_row_related_field_id": 5741,
                "has_related_field": True,
            },
        ],
        "views": [],
        "rows": [
            {
                "id": 1,
                "order": 1,
                "field_5736": "t1",
                "field_5737": "A",
                "field_5738": "A",
                "field_5742": [1],
            },
        ],
    },
    {
        "id": 601,
        "name": "t2",
        "order": 2,
        "fields": [
            {
                "id": 5739,
                "type": "text",
                "name": "name",
                "order": 0,
                "primary": True,
                "text_default": "",
            },
            {
                "id": 5740,
                "type": "formula",
                "name": "lookup",
                "order": 1,
                "primary": False,
                "nullable": True,
                "formula": "lookup('link', 'text')",
                "formula_type": "array",
                "array_formula_type": "text",
            },
            {
                "id": 5741,
                "type": "link_row",
                "name": "link",
                "order": 2,
                "primary": False,
                "link_row_table_id": 600,
                "link_row_related_field_id": 5742,
                "has_related_field": True,
            },
            {
                "id": 5743,
                "type": "lookup",
                "name": "lookup2",
                "order": 1,
                "primary": False,
                "nullable": True,
                "through_field_id": 5741,
                "through_field_name": "link",
                "target_field_id": 5737,
                "target_field_name": "formula",
            },
        ],
        "views": [],
        "rows": [
            {
                "id": 1,
                "order": 1,
                "field_5739": "t2",
                "field_5740": ["A"],
                "field_5741": [1],
                "field_5742": "t1",
            },
        ],
    },
]


@pytest.mark.django_db
def test_can_import_database_with_formula_dependencies(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    id_mapping = {}
    tables = DatabaseApplicationType().import_tables_serialized(
        database,
        EXPORTED_TABLES_WITH_DEPENDENCIES_EXAMPLE,
        id_mapping,
        ImportExportConfig(include_permission_data=False),
    )
    assert len(tables) == 2

    # Verify formulas are imported correctly and rows have correct values
    t1 = tables[0].get_model(attribute_names=True)
    r1 = t1.objects.get(pk=1)

    assert r1.formula == "A"

    t2 = tables[1].get_model(attribute_names=True)
    r2 = t2.objects.get(pk=1)

    assert r2.lookup == [{"id": 1, "value": "A"}]
    assert r2.lookup2 == [{"id": 1, "value": "A"}]


@pytest.mark.django_db
@pytest.mark.field_link_row
def test_get_via_dependants_of_link_field_num_queries_does_not_scale(data_fixture):
    table = data_fixture.create_database_table()
    linked_table = data_fixture.create_database_table(database=table.database)
    link_field = data_fixture.create_link_row_field(
        table=table, link_row_table=linked_table
    )
    dependency_field = data_fixture.create_text_field(table=table)

    def add_via_dependants(count):
        created_ids = []
        for _ in range(count):
            dependant = data_fixture.create_text_field(table=linked_table)
            FieldDependency.objects.create(
                dependency=dependency_field, dependant=dependant, via=link_field
            )
            created_ids.append(dependant.id)
        return created_ids

    def measure():
        with CaptureQueriesContext(connection) as ctx:
            dependants = FieldDependencyHandler.get_via_dependants_of_link_field(
                link_field.specific
            )
        return len(ctx.captured_queries), dependants

    first_ids = add_via_dependants(3)
    FieldDependencyHandler.get_via_dependants_of_link_field(link_field.specific)
    few_queries, few_dependants = measure()

    second_ids = add_via_dependants(3)
    FieldDependencyHandler.get_via_dependants_of_link_field(link_field.specific)
    more_queries, more_dependants = measure()

    assert more_queries == few_queries

    assert len(more_dependants) == len(few_dependants) + 3
    result_ids = {field.id for field, _, _ in more_dependants}
    assert set(first_ids) | set(second_ids) <= result_ids
    for field, field_type, via_path in more_dependants:
        assert via_path == []
        assert field_type == field_type_registry.get_by_model(field)


@pytest.mark.django_db
@override_settings(MAX_FIELD_REFERENCE_DEPTH=3)
def test_get_all_dependant_fields_stops_recursing_on_cyclic_dependency(data_fixture):
    """
    The recursive dependants query used to only apply the max depth to its final
    result, so a cycle in the dependency rows made it recurse without bound and
    spill temporary files until the disk was full. The recursion itself must stop
    at the configured max depth.
    """

    field_a = data_fixture.create_text_field()
    field_b = data_fixture.create_text_field(table=field_a.table)
    # Insert the cycle directly, bypassing the checks that normally prevent it.
    FieldDependency.objects.create(dependant=field_a, dependency=field_a)
    FieldDependency.objects.create(dependant=field_a, dependency=field_b)
    FieldDependency.objects.create(dependant=field_b, dependency=field_a)

    # The query must return, after which the cycle is reported as such rather
    # than hanging Postgres.
    with pytest.raises(CircularFieldDependencyError):
        FieldDependencyHandler.group_all_dependent_fields_by_level(
            field_a.table_id,
            [field_a.id],
            FieldCache(),
            associated_relations_changed=False,
            database_id_prefilter=field_a.table.database_id,
        )
