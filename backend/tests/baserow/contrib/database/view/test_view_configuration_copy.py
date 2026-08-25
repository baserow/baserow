from unittest.mock import patch

import pytest

from baserow.contrib.database.views.exceptions import (
    CannotCopyViewConfigurationToSameView,
    ViewConfigurationCopyCategoryNotSupported,
    ViewNotInTable,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import (
    ViewDefaultValue,
    ViewFilter,
    ViewGroupBy,
    ViewSort,
)
from baserow.contrib.database.views.registries import (
    decorator_type_registry,
    view_type_registry,
)
from baserow.core.exceptions import UserNotInWorkspace


def test_get_copyable_configuration_categories_per_view_type():
    grid = view_type_registry.get("grid")
    gallery = view_type_registry.get("gallery")
    form = view_type_registry.get("form")

    assert grid.get_copyable_configuration_categories() == {
        "field_visibility",
        "field_order",
        "field_widths",
        "view_settings",
        "filters",
        "sorts",
        "group_bys",
        "decorations",
        "default_row_values",
    }
    assert gallery.get_copyable_configuration_categories() == {
        "field_visibility",
        "field_order",
        "filters",
        "sorts",
        "decorations",
        "default_row_values",
    }
    assert form.get_copyable_configuration_categories() == set()


@pytest.mark.django_db
def test_copy_view_configuration_filters(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(
        table=table, filter_type="OR", filters_disabled=True
    )
    dest_view = data_fixture.create_grid_view(table=table)

    root_group = data_fixture.create_view_filter_group(
        view=source_view, filter_type="OR"
    )
    nested_group = data_fixture.create_view_filter_group(
        view=source_view, parent_group=root_group
    )
    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )
    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="b", group=root_group
    )
    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="c", group=nested_group
    )

    # The destination has an existing filter that must be replaced.
    existing_filter = data_fixture.create_view_filter(
        view=dest_view, field=field, type="equal", value="old"
    )

    ViewHandler().copy_view_configuration(user, source_view, dest_view, ["filters"])

    dest_view.refresh_from_db()
    assert dest_view.filter_type == "OR"
    assert dest_view.filters_disabled is True

    assert not ViewFilter.objects.filter(id=existing_filter.id).exists()

    dest_groups = list(dest_view.filter_groups.all().order_by("id"))
    assert len(dest_groups) == 2
    assert dest_groups[0].filter_type == "OR"
    assert dest_groups[0].parent_group_id is None
    assert dest_groups[1].parent_group_id == dest_groups[0].id
    # New ids are generated, the source objects are not reused.
    source_group_ids = {root_group.id, nested_group.id}
    assert source_group_ids.isdisjoint({group.id for group in dest_groups})

    dest_filters = list(dest_view.viewfilter_set.all().order_by("id"))
    assert [
        (view_filter.value, view_filter.group_id) for view_filter in dest_filters
    ] == [
        ("a", None),
        ("b", dest_groups[0].id),
        ("c", dest_groups[1].id),
    ]

    # The source view is untouched.
    assert source_view.viewfilter_set.count() == 3
    assert source_view.filter_groups.count() == 2


@pytest.mark.django_db
def test_copy_view_configuration_sorts_group_bys_and_decorations(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    other_field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)

    data_fixture.create_view_sort(view=source_view, field=field, order="DESC")
    data_fixture.create_view_group_by(
        view=source_view, field=field, order="ASC", width=250
    )
    data_fixture.create_view_decoration(
        view=source_view, value_provider_conf={"config": 1}
    )

    data_fixture.create_view_sort(view=dest_view, field=other_field, order="ASC")
    data_fixture.create_view_group_by(view=dest_view, field=other_field)
    data_fixture.create_view_decoration(view=dest_view)

    ViewHandler().copy_view_configuration(
        user, source_view, dest_view, ["sorts", "group_bys", "decorations"]
    )

    dest_sorts = list(dest_view.viewsort_set.all())
    assert [(sort.field_id, sort.order) for sort in dest_sorts] == [(field.id, "DESC")]
    dest_group_bys = list(dest_view.viewgroupby_set.all())
    assert [
        (group_by.field_id, group_by.order, group_by.width)
        for group_by in dest_group_bys
    ] == [(field.id, "ASC", 250)]
    dest_decorations = list(dest_view.viewdecoration_set.all())
    assert [
        (decoration.type, decoration.value_provider_conf)
        for decoration in dest_decorations
    ] == [("tmp_decorator_type_1", {"config": 1})]

    assert source_view.viewsort_set.count() == 1
    assert source_view.viewgroupby_set.count() == 1
    assert source_view.viewdecoration_set.count() == 1


@pytest.mark.django_db
def test_copy_view_configuration_field_options_and_row_height(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(
        table=table,
        row_height_size="large",
        frozen_column_count=3,
        row_identifier_type="count",
    )
    dest_view = data_fixture.create_grid_view(table=table, row_height_size="small")

    source_view.get_field_options(create_if_missing=True)
    source_options = source_view.gridviewfieldoptions_set.get(field=field)
    source_options.hidden = True
    source_options.order = 2
    source_options.width = 300
    source_options.save()

    ViewHandler().copy_view_configuration(
        user,
        source_view,
        dest_view,
        ["field_visibility", "field_widths", "view_settings"],
    )

    dest_view.refresh_from_db()
    assert dest_view.row_height_size == "large"
    assert dest_view.frozen_column_count == 3
    assert dest_view.row_identifier_type == "count"
    dest_options = dest_view.gridviewfieldoptions_set.get(field=field)
    assert dest_options.hidden is True
    assert dest_options.width == 300
    # The `field_order` category was not requested, so the order is untouched.
    assert dest_options.order != 2


@pytest.mark.django_db
def test_copy_view_configuration_default_row_values(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)

    ViewDefaultValue.objects.create(
        view=source_view, field=field, value="default", field_type="text"
    )
    ViewDefaultValue.objects.create(
        view=dest_view, field=field, value="old", field_type="text"
    )

    ViewHandler().copy_view_configuration(
        user, source_view, dest_view, ["default_row_values"]
    )

    dest_default_values = list(dest_view.view_default_values.all())
    assert [
        (default_value.field_id, default_value.value)
        for default_value in dest_default_values
    ] == [(field.id, "default")]


@pytest.mark.django_db
def test_copy_view_configuration_validation(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    other_table = data_fixture.create_database_table(user=user)
    grid_view = data_fixture.create_grid_view(table=table)
    other_grid_view = data_fixture.create_grid_view(table=table)
    gallery_view = data_fixture.create_gallery_view(table=table)
    other_table_view = data_fixture.create_grid_view(table=other_table)

    handler = ViewHandler()

    with pytest.raises(CannotCopyViewConfigurationToSameView):
        handler.copy_view_configuration(user, grid_view, grid_view, ["filters"])

    with pytest.raises(ViewNotInTable):
        handler.copy_view_configuration(user, other_table_view, grid_view, ["filters"])

    # The gallery view doesn't support the grid specific categories, in either
    # direction.
    with pytest.raises(ViewConfigurationCopyCategoryNotSupported) as exc:
        handler.copy_view_configuration(
            user, grid_view, gallery_view, ["filters", "view_settings", "unknown"]
        )
    assert exc.value.categories == ["unknown", "view_settings"]

    with pytest.raises(ViewConfigurationCopyCategoryNotSupported):
        handler.copy_view_configuration(
            user, gallery_view, other_grid_view, ["field_widths"]
        )


@pytest.mark.django_db
def test_copy_view_configuration_replaces_config_on_trashed_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    trashed_field = data_fixture.create_text_field(table=table, trashed=True)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)

    # Configuration on trashed fields is hidden by the default managers, but
    # deliberately kept so that it restores together with the field.
    hidden_source_filter = data_fixture.create_view_filter(
        view=source_view, field=trashed_field, type="equal", value="hidden"
    )
    hidden_dest_group = data_fixture.create_view_filter_group(view=dest_view)
    hidden_dest_filter = data_fixture.create_view_filter(
        view=dest_view,
        field=trashed_field,
        type="equal",
        value="old hidden",
        group=hidden_dest_group,
    )
    hidden_dest_sort = data_fixture.create_view_sort(
        view=dest_view, field=trashed_field
    )

    handler = ViewHandler()
    original_configuration = handler.export_view_configuration(
        dest_view, ["filters", "sorts"]
    )
    handler.copy_view_configuration(user, source_view, dest_view, ["filters", "sorts"])

    # The destination's hidden configuration is replaced too, and the source's
    # hidden filter is copied along, staying hidden until the field restores.
    dest_filters = ViewFilter._base_manager.filter(view=dest_view)
    assert not dest_filters.filter(id=hidden_dest_filter.id).exists()
    assert not ViewSort._base_manager.filter(id=hidden_dest_sort.id).exists()
    assert list(dest_filters.values_list("value", flat=True)) == ["hidden"]

    # Restoring the previous configuration brings the hidden objects back with
    # their original ids.
    handler.apply_view_configuration(
        user, dest_view, original_configuration, preserve_ids=True
    )
    assert ViewFilter._base_manager.filter(id=hidden_dest_filter.id).exists()
    assert ViewSort._base_manager.filter(id=hidden_dest_sort.id).exists()


@pytest.mark.django_db
def test_copy_view_configuration_restores_field_options_of_trashed_fields(
    data_fixture,
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    trashed_field = data_fixture.create_text_field(table=table, trashed=True)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)

    options_model = dest_view.gridviewfieldoptions_set.model
    options_model.objects_and_trash.create(
        grid_view=source_view, field=trashed_field, hidden=False
    )
    dest_options = options_model.objects_and_trash.create(
        grid_view=dest_view, field=trashed_field, hidden=True
    )

    handler = ViewHandler()
    original_configuration = handler.export_view_configuration(
        dest_view, ["field_visibility"]
    )
    handler.copy_view_configuration(user, source_view, dest_view, ["field_visibility"])

    dest_options.refresh_from_db()
    assert dest_options.hidden is False

    # Undoing restores the trashed field's option, so it is still correct when
    # the field is restored from the trash.
    handler.apply_view_configuration(
        user, dest_view, original_configuration, preserve_ids=True
    )
    dest_options.refresh_from_db()
    assert dest_options.hidden is True


@pytest.mark.django_db
def test_copy_view_configuration_cross_view_type(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_gallery_view(table=table)

    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )
    source_view.get_field_options(create_if_missing=True)
    source_options = source_view.gridviewfieldoptions_set.get(field=field)
    source_options.hidden = True
    source_options.save()

    ViewHandler().copy_view_configuration(
        user, source_view, dest_view, ["filters", "field_visibility"]
    )

    assert dest_view.viewfilter_set.count() == 1
    dest_options = dest_view.galleryviewfieldoptions_set.get(field=field)
    assert dest_options.hidden is True


@pytest.mark.django_db
def test_copy_view_configuration_without_permissions(data_fixture):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)

    with pytest.raises(UserNotInWorkspace):
        ViewHandler().copy_view_configuration(
            other_user, source_view, dest_view, ["filters"]
        )


@pytest.mark.django_db
def test_apply_view_configuration_without_permissions(data_fixture):
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    view = data_fixture.create_grid_view(table=table)

    handler = ViewHandler()
    configuration = handler.export_view_configuration(view, ["filters"])

    # The permission is checked in `apply_view_configuration` itself so that
    # undoing and redoing a copy also re-checks it.
    with pytest.raises(UserNotInWorkspace):
        handler.apply_view_configuration(other_user, view, configuration)


@pytest.mark.django_db
def test_apply_view_configuration_preserve_ids(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    view_filter = data_fixture.create_view_filter(
        view=view, field=field, type="equal", value="a"
    )
    view_sort = data_fixture.create_view_sort(view=view, field=field)
    view_group_by = data_fixture.create_view_group_by(view=view, field=field)

    handler = ViewHandler()
    categories = ["filters", "sorts", "group_bys"]
    configuration = handler.export_view_configuration(view, categories)

    # Change the configuration so that the restore is observable.
    view.viewfilter_set.all().delete()
    view.viewsort_set.all().delete()
    view.viewgroupby_set.all().delete()

    handler.apply_view_configuration(user, view, configuration, preserve_ids=True)

    assert ViewFilter.objects.get(view=view).id == view_filter.id
    assert ViewSort.objects.get(view=view).id == view_sort.id
    assert ViewGroupBy.objects.get(view=view).id == view_group_by.id


@pytest.mark.django_db
def test_apply_view_configuration_skips_deleted_fields(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    deleted_field = data_fixture.create_text_field(table=table)
    view = data_fixture.create_grid_view(table=table)

    data_fixture.create_view_filter(view=view, field=field, type="equal", value="a")
    data_fixture.create_view_filter(
        view=view, field=deleted_field, type="equal", value="b"
    )

    handler = ViewHandler()
    configuration = handler.export_view_configuration(view, ["filters"])

    deleted_field.delete()

    handler.apply_view_configuration(user, view, configuration, preserve_ids=True)

    assert [view_filter.field_id for view_filter in view.viewfilter_set.all()] == [
        field.id
    ]


@pytest.mark.django_db
def test_copy_view_configuration_calls_decorator_type_hook(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_decoration(view=source_view)

    # The decorations are bulk created without the handler's create method, but
    # the decorator type hook must still run because it can enforce
    # constraints, a premium license for example.
    with patch.object(
        decorator_type_registry.get("tmp_decorator_type_1"),
        "before_create_decoration",
    ) as before_create_mock:
        ViewHandler().copy_view_configuration(
            user, source_view, dest_view, ["decorations"]
        )

    before_create_mock.assert_called_once_with(dest_view, user)


@pytest.mark.django_db
def test_copy_view_configuration_notifies_view_subscriptions(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )

    # Copying filters changes which rows match the view, so the view
    # subscriptions must be notified for the rows entered/exited webhooks.
    with patch(
        "baserow.contrib.database.views.receivers.ViewSubscriptionHandler"
        ".notify_table_views_updates"
    ) as notify_mock:
        ViewHandler().copy_view_configuration(user, source_view, dest_view, ["filters"])

    notify_mock.assert_called_once_with([dest_view])

    # The other categories can't change which rows are in the view, so no
    # recomputation is triggered for them.
    with patch(
        "baserow.contrib.database.views.receivers.ViewSubscriptionHandler"
        ".notify_table_views_updates"
    ) as notify_mock:
        ViewHandler().copy_view_configuration(
            user, source_view, dest_view, ["sorts", "field_visibility"]
        )

    notify_mock.assert_not_called()


@pytest.mark.django_db
def test_copy_view_configuration_sends_single_signal(data_fixture):
    from baserow.contrib.database.views.signals import view_configuration_changed

    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )
    data_fixture.create_view_sort(view=source_view, field=field)

    received = []

    def receiver(sender, view, user, **kwargs):
        received.append(view)

    view_configuration_changed.connect(receiver)
    try:
        ViewHandler().copy_view_configuration(
            user, source_view, dest_view, ["filters", "sorts"]
        )
    finally:
        view_configuration_changed.disconnect(receiver)

    assert len(received) == 1
    assert received[0].id == dest_view.id
