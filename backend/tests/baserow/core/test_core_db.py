from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.db.models import CharField, Prefetch, Value
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Concat
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import (
    Field,
    LongTextField,
    SelectOption,
    TextField,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.models import (
    GalleryView,
    GridView,
    View,
    ViewFilter,
)
from baserow.core.db import (
    CombinedForeignKeyAndManyToManyMultipleFieldPrefetch,
    LockedAtomicTransaction,
    MultiFieldPrefetchQuerysetMixin,
    QuerySet,
    specific_iterator,
    specific_queryset,
)
from baserow.core.models import Settings, Workspace


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_locked_atomic_transaction(api_client, data_fixture):
    def is_locked(model):
        with connection.cursor() as cursor:
            table_name = model._meta.db_table
            cursor.execute(
                "select count(*) from pg_locks l join pg_class t on l.relation = "
                "t.oid WHERE relname = %(table_name)s;",
                {"table_name": table_name},
            )
            return cursor.fetchone()[0] > 0

    assert not is_locked(Settings)

    with LockedAtomicTransaction(Settings):
        assert is_locked(Settings)


@pytest.mark.django_db
def test_specific_iterator(data_fixture, django_assert_num_queries):
    text_field_1 = data_fixture.create_text_field()
    text_field_2 = data_fixture.create_text_field()
    text_field_3 = data_fixture.create_text_field()

    long_text_field_1 = data_fixture.create_long_text_field()
    long_text_field_2 = data_fixture.create_long_text_field()
    long_text_field_3 = data_fixture.create_long_text_field()

    base_queryset = Field.objects.filter(
        id__in=[
            text_field_1.id,
            text_field_2.id,
            text_field_3.id,
            long_text_field_1.id,
            long_text_field_2.id,
            long_text_field_3.id,
        ]
    ).order_by("id")

    with django_assert_num_queries(3):
        specific_objects = list(specific_iterator(base_queryset))

        assert isinstance(specific_objects[0], TextField)
        assert specific_objects[0].id == text_field_1.id

        assert isinstance(specific_objects[1], TextField)
        assert specific_objects[1].id == text_field_2.id

        assert isinstance(specific_objects[2], TextField)
        assert specific_objects[2].id == text_field_3.id

        assert isinstance(specific_objects[3], LongTextField)
        assert specific_objects[3].id == long_text_field_1.id

        assert isinstance(specific_objects[4], LongTextField)
        assert specific_objects[4].id == long_text_field_2.id

        assert isinstance(specific_objects[5], LongTextField)
        assert specific_objects[5].id == long_text_field_3.id


@pytest.mark.django_db
def test_specific_iterator_with_deleted_type(data_fixture, django_assert_num_queries):
    user = data_fixture.create_user()
    field_2 = data_fixture.create_text_field(user=user)

    # This field does not have a type, so we don't expect it to end up in the
    # specific objects.
    Field.objects.create(
        table=data_fixture.create_database_table(),
        order=1,
        name="Test",
        primary=False,
        content_type=field_2.content_type,
    )

    base_queryset = Field.objects.all()

    with pytest.raises(Field.DoesNotExist):
        list(specific_iterator(base_queryset))


@pytest.mark.django_db
def test_specific_iterator_with_trashed_objects(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    field = data_fixture.create_text_field(user=user)
    FieldHandler().delete_field(user=user, field=field)

    base_queryset = Field.objects_and_trash.all()
    specific_objects = list(specific_iterator(base_queryset))
    assert len(specific_objects) == 1


@pytest.mark.django_db
def test_specific_iterator_respecting_order(data_fixture, django_assert_num_queries):
    text_field_1 = data_fixture.create_text_field()
    long_text_field_1 = data_fixture.create_long_text_field()

    base_queryset = Field.objects.filter(
        id__in=[
            text_field_1.id,
            long_text_field_1.id,
        ]
    ).order_by("-id")

    specific_objects = list(specific_iterator(base_queryset))
    assert specific_objects[0].id == long_text_field_1.id
    assert specific_objects[1].id == text_field_1.id


@pytest.mark.django_db
def test_specific_iterator_with_annotation(data_fixture, django_assert_num_queries):
    text_field_1 = data_fixture.create_text_field()
    text_field_2 = data_fixture.create_text_field()

    base_queryset = (
        Field.objects.filter(
            id__in=[
                text_field_1.id,
                text_field_2.id,
            ]
        )
        .annotate(
            tmp_test_annotation=ExpressionWrapper(
                Concat(Value("test"), "id"),
                output_field=CharField(),
            )
        )
        .order_by("id")
    )

    with django_assert_num_queries(2):
        specific_objects = list(specific_iterator(base_queryset))

    assert specific_objects[0].tmp_test_annotation == f"test{text_field_1.id}"
    assert specific_objects[1].tmp_test_annotation == f"test{text_field_2.id}"


@pytest.mark.django_db
def test_specific_iterator_with_select_related(data_fixture, django_assert_num_queries):
    grid_view = data_fixture.create_grid_view()
    gallery_view = data_fixture.create_gallery_view()
    data_fixture.create_view_filter(view=grid_view)
    data_fixture.create_view_filter(view=gallery_view)
    data_fixture.create_view_filter(view=gallery_view)

    base_queryset = View.objects.filter(
        id__in=[
            grid_view.id,
            gallery_view.id,
        ]
    ).select_related("content_type")

    with django_assert_num_queries(3):
        specific_objects = list(specific_iterator(base_queryset))
        assert isinstance(specific_objects[0].content_type, ContentType)
        assert isinstance(specific_objects[1].content_type, ContentType)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "prefetch_related",
    ["viewfilter_set", Prefetch("viewfilter_set", queryset=ViewFilter.objects.all())],
)
def test_specific_iterator_with_prefetch_related(
    prefetch_related, data_fixture, django_assert_num_queries
):
    grid_view = data_fixture.create_grid_view()
    gallery_view = data_fixture.create_gallery_view()
    filter_1 = data_fixture.create_view_filter(view=grid_view)
    filter_2 = data_fixture.create_view_filter(view=gallery_view)
    filter_3 = data_fixture.create_view_filter(view=gallery_view)

    base_queryset = (
        View.objects.filter(
            id__in=[
                grid_view.id,
                gallery_view.id,
            ]
        )
        .order_by("id")
        .prefetch_related(prefetch_related)
    )

    with django_assert_num_queries(4):
        specific_objects = list(specific_iterator(base_queryset))
        all_1 = specific_objects[0].viewfilter_set.all()
        assert [f.id for f in all_1] == [filter_1.id]
        all_2 = specific_objects[1].viewfilter_set.all()
        assert [f.id for f in all_2] == [filter_2.id, filter_3.id]


@pytest.mark.django_db
def test_specific_iterator_per_content_type(data_fixture, django_assert_num_queries):
    table = data_fixture.create_database_table()
    data_fixture.create_text_field()
    data_fixture.create_text_field()
    grid_view_1 = data_fixture.create_grid_view(table=table)
    grid_view_2 = data_fixture.create_grid_view(table=table)
    gallery_view_1 = data_fixture.create_gallery_view(table=table)
    gallery_view_2 = data_fixture.create_gallery_view(table=table)

    base_queryset = (
        View.objects.filter(
            id__in=[
                grid_view_1.id,
                grid_view_2.id,
                gallery_view_1.id,
                gallery_view_2.id,
            ]
        )
        .prefetch_related("viewfilter_set")
        .order_by("id")
    )

    with django_assert_num_queries(6):

        def hook(model, queryset):
            if model == GridView:
                queryset = queryset.prefetch_related("gridviewfieldoptions_set")
            if model == GalleryView:
                queryset = queryset.prefetch_related("galleryviewfieldoptions_set")
            return queryset

        specific_objects = list(
            specific_iterator(base_queryset, per_content_type_queryset_hook=hook)
        )
        list(specific_objects[0].gridviewfieldoptions_set.all())
        list(specific_objects[0].viewfilter_set.all())
        list(specific_objects[1].gridviewfieldoptions_set.all())
        list(specific_objects[1].viewfilter_set.all())
        list(specific_objects[2].galleryviewfieldoptions_set.all())
        list(specific_objects[2].viewfilter_set.all())
        list(specific_objects[3].galleryviewfieldoptions_set.all())
        list(specific_objects[3].viewfilter_set.all())


@pytest.mark.django_db
def test_specific_iterator_per_content_type_with_nested_prefetch(
    data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    data_fixture.create_text_field()
    data_fixture.create_text_field()
    grid_view_1 = data_fixture.create_grid_view(table=table)
    grid_view_2 = data_fixture.create_grid_view(table=table)
    gallery_view_1 = data_fixture.create_gallery_view(table=table)
    gallery_view_2 = data_fixture.create_gallery_view(table=table)

    base_queryset = View.objects.filter(
        id__in=[
            grid_view_1.id,
            grid_view_2.id,
            gallery_view_1.id,
            gallery_view_2.id,
        ]
    ).prefetch_related("table__field_set")

    with django_assert_num_queries(5):
        specific_objects = list(specific_iterator(base_queryset))
        list(specific_objects[0].table.field_set.all())
        list(specific_objects[1].table.field_set.all())
        list(specific_objects[2].table.field_set.all())
        list(specific_objects[3].table.field_set.all())


@pytest.mark.django_db
def test_specific_iterator_with_list(data_fixture, django_assert_num_queries):
    table = data_fixture.create_database_table()
    data_fixture.create_text_field()
    data_fixture.create_text_field()
    grid_view_1 = data_fixture.create_grid_view(table=table)
    grid_view_2 = data_fixture.create_grid_view(table=table)
    gallery_view_1 = data_fixture.create_gallery_view(table=table)
    gallery_view_2 = data_fixture.create_gallery_view(table=table)

    views = list(
        View.objects.filter(
            id__in=[
                grid_view_1.id,
                grid_view_2.id,
                gallery_view_1.id,
                gallery_view_2.id,
            ]
        ).order_by("id")
    )

    with django_assert_num_queries(2):
        specific_objects = list(specific_iterator(views, base_model=View))

        assert isinstance(specific_objects[0], GridView)
        assert specific_objects[0].id == grid_view_1.id

        assert isinstance(specific_objects[1], GridView)
        assert specific_objects[1].id == grid_view_2.id

        assert isinstance(specific_objects[2], GalleryView)
        assert specific_objects[2].id == gallery_view_1.id

        assert isinstance(specific_objects[3], GalleryView)
        assert specific_objects[3].id == gallery_view_2.id


@pytest.mark.django_db
def test_specific_iterator_with_list_without_providing_base_model(
    data_fixture, django_assert_num_queries
):
    with pytest.raises(ValueError):
        list(specific_iterator([]))


@pytest.mark.django_db
def test_specific_iterator_with_list_with_select_related_keys(
    data_fixture, django_assert_num_queries
):
    table = data_fixture.create_database_table()
    data_fixture.create_text_field()
    data_fixture.create_text_field()
    grid_view_1 = data_fixture.create_grid_view(table=table)
    grid_view_2 = data_fixture.create_grid_view(table=table)
    gallery_view_1 = data_fixture.create_gallery_view(table=table)
    gallery_view_2 = data_fixture.create_gallery_view(table=table)

    views = list(
        View.objects.filter(
            id__in=[
                grid_view_1.id,
                grid_view_2.id,
                gallery_view_1.id,
                gallery_view_2.id,
            ]
        ).select_related("content_type")
    )

    with django_assert_num_queries(2):
        specific_objects = list(
            specific_iterator(views, base_model=View, select_related=["content_type"])
        )

        str(specific_objects[0].content_type.id)
        str(specific_objects[1].content_type.id)
        str(specific_objects[2].content_type.id)
        str(specific_objects[3].content_type.id)


@pytest.mark.django_db
def test_specific_queryset(data_fixture, django_assert_num_queries):
    text_field_1 = data_fixture.create_text_field()
    text_field_2 = data_fixture.create_text_field()

    long_text_field_1 = data_fixture.create_long_text_field()
    long_text_field_2 = data_fixture.create_long_text_field()

    queryset = Field.objects.all()
    queryset = specific_queryset(queryset)
    queryset = queryset.filter(
        id__in=[
            text_field_1.id,
            text_field_2.id,
            long_text_field_1.id,
            long_text_field_2.id,
        ]
    ).order_by("id")

    with django_assert_num_queries(3):
        specific_objects = list(queryset)

        assert isinstance(specific_objects[0], TextField)
        assert specific_objects[0].id == text_field_1.id

        assert isinstance(specific_objects[1], TextField)
        assert specific_objects[1].id == text_field_2.id

        assert isinstance(specific_objects[2], LongTextField)
        assert specific_objects[2].id == long_text_field_1.id

        assert isinstance(specific_objects[3], LongTextField)
        assert specific_objects[3].id == long_text_field_2.id


@pytest.mark.django_db
def test_specific_queryset_with_select_related(data_fixture, django_assert_num_queries):
    grid_view = data_fixture.create_grid_view()
    gallery_view = data_fixture.create_gallery_view()
    data_fixture.create_view_filter(view=grid_view)
    data_fixture.create_view_filter(view=gallery_view)
    data_fixture.create_view_filter(view=gallery_view)

    base_queryset = (
        specific_queryset(View.objects.all())
        .filter(
            id__in=[
                grid_view.id,
                gallery_view.id,
            ]
        )
        .select_related("content_type")
    )

    with django_assert_num_queries(3):
        specific_objects = list(base_queryset)
        assert isinstance(specific_objects[0].content_type, ContentType)
        assert isinstance(specific_objects[1].content_type, ContentType)


@pytest.mark.django_db
def test_multi_field_prefetch(data_fixture):
    data_fixture.create_workspace()
    data_fixture.create_workspace()

    class TemporaryWorkspaceQueryset(MultiFieldPrefetchQuerysetMixin, QuerySet):
        pass

    class TemporaryWorkspace(Workspace):
        temporary_multi_field_objects = TemporaryWorkspaceQueryset.as_manager()

        class Meta:
            proxy = True
            app_label = Workspace._meta.app_label

    prefetch_function = MagicMock()
    prefetch_function_2 = MagicMock()

    queryset = (
        TemporaryWorkspace.temporary_multi_field_objects.all().multi_field_prefetch(
            prefetch_function
        )
    )
    list(queryset)

    prefetch_function.assert_called_once()
    assert isinstance(prefetch_function.call_args[0][0], TemporaryWorkspaceQueryset)

    queryset = queryset.multi_field_prefetch(prefetch_function_2)
    list(queryset)

    assert prefetch_function.call_count == 2
    prefetch_function_2.assert_called_once()


# CombinedForeignKeyAndManyToManyMultipleFieldPrefetch
@pytest.mark.django_db
def test_combined_foreign_key_and_many_to_many_multiple_field_prefetch(
    data_fixture, django_assert_num_queries
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)

    single_select_field = data_fixture.create_single_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    option_a = data_fixture.create_select_option(
        field=single_select_field, value="A", color="blue", order=0
    )
    option_b = data_fixture.create_select_option(
        field=single_select_field, value="B", color="red", order=1
    )
    data_fixture.create_select_option(
        field=single_select_field, value="C", color="red", order=2
    )

    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )
    option_1 = data_fixture.create_select_option(
        field=multiple_select_field, value="A", color="blue", order=0
    )
    option_2 = data_fixture.create_select_option(
        field=multiple_select_field, value="B", color="red", order=1
    )
    data_fixture.create_select_option(
        field=multiple_select_field, value="C", color="red", order=2
    )

    handler = RowHandler()
    handler.create_rows(
        user=user,
        table=table,
        rows_values=[
            {
                f"field_{single_select_field.id}": option_a.id,
                f"field_{multiple_select_field.id}": [option_1.id],
            },
            {
                f"field_{single_select_field.id}": option_b.id,
                f"field_{multiple_select_field.id}": [option_2.id, option_1.id],
            },
            {
                f"field_{single_select_field.id}": None,
                f"field_{multiple_select_field.id}": [],
            },
        ],
    )

    model = table.get_model()
    queryset = model.objects.all().multi_field_prefetch(
        CombinedForeignKeyAndManyToManyMultipleFieldPrefetch(
            SelectOption, [f"field_{single_select_field.id}"], skip_target_check=True
        ).add_field_names([f"field_{multiple_select_field.id}"])
    )

    # We expect three queries. One to fetch the rows, one to fetch the manytomany
    # relations, and one to fetch the select options.
    with django_assert_num_queries(3):
        rows = list(queryset)
        assert getattr(rows[0], f"field_{single_select_field.id}").id == option_a.id
        assert [
            v.id for v in getattr(rows[0], f"field_{multiple_select_field.id}").all()
        ] == [option_1.id]
        assert getattr(rows[1], f"field_{single_select_field.id}").id == option_b.id
        assert [
            v.id for v in getattr(rows[1], f"field_{multiple_select_field.id}").all()
        ] == [
            option_2.id,
            option_1.id,
        ]
        assert getattr(rows[2], f"field_{single_select_field.id}_id") is None
        assert [
            v.id for v in getattr(rows[2], f"field_{multiple_select_field.id}").all()
        ] == []


@pytest.mark.django_db
def test_combined_multiple_field_prefetch_different_foreign_key_target(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)

    single_select_field = data_fixture.create_single_select_field(
        table=table, name="option_field", order=1, primary=True
    )

    model = table.get_model()

    with pytest.raises(ValueError):
        list(
            model.objects.all().multi_field_prefetch(
                CombinedForeignKeyAndManyToManyMultipleFieldPrefetch(
                    Workspace, [f"field_{single_select_field.id}"]
                )
            )
        )


@pytest.mark.django_db
def test_multiple_field_prefetch_different_many_to_many_target(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )

    model = table.get_model()

    with pytest.raises(ValueError):
        list(
            model.objects.all().multi_field_prefetch(
                CombinedForeignKeyAndManyToManyMultipleFieldPrefetch(
                    Workspace, [f"field_{multiple_select_field.id}"]
                )
            )
        )


@pytest.mark.django_db
def test_multiple_field_prefetch__many_to_many_no_results(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="option_field", order=1, primary=True
    )

    model = table.get_model()

    assert (
        list(
            model.objects.all().multi_field_prefetch(
                CombinedForeignKeyAndManyToManyMultipleFieldPrefetch(
                    SelectOption,
                    [f"field_{multiple_select_field.id}"],
                    skip_target_check=True,
                )
            )
        )
        == []
    )


@pytest.mark.django_db
def test_multiple_field_prefetch__many_to_many_missing_source(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(name="Car", user=user)
    multiple_select_field = data_fixture.create_multiple_select_field(
        table=table, name="field", order=1, primary=True
    )
    option_a = data_fixture.create_select_option(
        field=multiple_select_field, value="A", color="blue", order=0
    )
    option_b = data_fixture.create_select_option(
        field=multiple_select_field, value="B", color="red", order=1
    )

    model = table.get_model(attribute_names=True)
    row = model.objects.create()
    row.field.add(option_a.id, option_b.id)

    option_a.delete()

    assert len(row.field.all()) == 1

    rows = list(
        model.objects.all().multi_field_prefetch(
            CombinedForeignKeyAndManyToManyMultipleFieldPrefetch(
                SelectOption, ["field"], skip_target_check=True
            )
        )
    )
    row = rows[0]
    assert len(row.field.all()) == 1


@pytest.mark.django_db
def test_specific_iterator_skip_missing_specific_objects(data_fixture):
    """
    Tests the optional skip_missing_specific_objects argument.

    When True, a missing specific instance shouldn't raise an exception.
    """

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)

    # Create a field without a specific type (simulating data integrity issue)
    field_without_specific = Field.objects.create(
        table=table,
        order=1,
        name="Test",
        primary=False,
        content_type=field.content_type,
    )

    base_queryset = Field.objects.filter(
        id__in=[field.id, field_without_specific.id]
    ).order_by("id")

    # Without skip_missing_specific_objects, the 2nd field should
    # cause an exception
    with pytest.raises(Field.DoesNotExist):
        list(specific_iterator(base_queryset))

    # With skip_missing_specific_objects, the 2nd field should be
    # skipped gracefully
    with patch("baserow.core.db.logger") as mock_logger:
        specific_objects = list(
            specific_iterator(base_queryset, skip_missing_specific_objects=True)
        )

    # Should only return the 1 specific field, skipping the one without
    # a specific instance
    assert len(specific_objects) == 1
    assert specific_objects[0].id == field.id
    mock_logger.error.assert_called_once_with(
        f"The specific object with id {field_without_specific.id} does not exist."
    )
