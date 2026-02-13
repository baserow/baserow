from django.db import IntegrityError

import pytest

from baserow_premium.views.models import (
    CalendarViewFieldOptions,
    KanbanViewFieldOptions,
)


@pytest.mark.django_db
def test_kanban_view_field_options_manager_view_trashed(premium_data_fixture):
    kanban_view = premium_data_fixture.create_kanban_view()

    # create_kanban_view already creates a view field option
    # which we don't want to test here
    KanbanViewFieldOptions.objects.all().delete()

    field = premium_data_fixture.create_text_field(table=kanban_view.table)
    premium_data_fixture.create_kanban_view_field_option(kanban_view, field)

    assert KanbanViewFieldOptions.objects.count() == 1

    kanban_view.trashed = True
    kanban_view.save()

    assert KanbanViewFieldOptions.objects.count() == 0


@pytest.mark.django_db
def test_kanban_view_field_options_manager_field_trashed(premium_data_fixture):
    kanban_view = premium_data_fixture.create_kanban_view()

    # create_kanban_view already creates a view field option
    # which we don't want to test here
    KanbanViewFieldOptions.objects.all().delete()

    field = premium_data_fixture.create_text_field(table=kanban_view.table)
    premium_data_fixture.create_kanban_view_field_option(kanban_view, field)

    assert KanbanViewFieldOptions.objects.count() == 1

    field.trashed = True
    field.save()

    assert KanbanViewFieldOptions.objects.count() == 0


@pytest.mark.once_per_day_in_ci
def test_migration_remove_duplicate_fieldoptions(
    premium_data_fixture, migrator, teardown_table_metadata
):
    migrate_from = [
        ("baserow_premium", "0012_migrate_old_comment_to_tiptap_message"),
    ]
    migrate_to = [("baserow_premium", "0014_add_unique_constraint_viewfieldoptions")]

    migrator.migrate(migrate_from)

    user = premium_data_fixture.create_user()
    workspace = premium_data_fixture.create_workspace(user=user)
    app = premium_data_fixture.create_database_application(
        workspace=workspace, name="Test 1"
    )
    table = premium_data_fixture.create_database_table(name="Cars", database=app)
    field = premium_data_fixture.create_text_field(table=table)

    # create_grid_view already create a GridViewFieldOption for every field
    kanban_view = premium_data_fixture.create_kanban_view(table=table)
    KanbanViewFieldOptions.objects.create(kanban_view=kanban_view, field=field)

    assert (
        KanbanViewFieldOptions.objects.filter(
            field=field, kanban_view=kanban_view
        ).count()
        == 2
    )

    calendar_view = premium_data_fixture.create_calendar_view(table=table)
    CalendarViewFieldOptions.objects.create(calendar_view=calendar_view, field=field)
    CalendarViewFieldOptions.objects.create(calendar_view=calendar_view, field=field)

    assert (
        CalendarViewFieldOptions.objects.filter(
            field=field, calendar_view=calendar_view
        ).count()
        == 3
    )

    # The migrations will remove duplicates and add a unique constraint.
    migrator.migrate(migrate_to)

    assert (
        KanbanViewFieldOptions.objects.filter(
            field=field, kanban_view=kanban_view
        ).count()
        == 1
    )
    assert (
        CalendarViewFieldOptions.objects.filter(
            field=field, calendar_view=calendar_view
        ).count()
        == 1
    )

    with pytest.raises(IntegrityError):
        KanbanViewFieldOptions.objects.create(kanban_view=kanban_view, field=field)

    with pytest.raises(IntegrityError):
        CalendarViewFieldOptions.objects.create(
            calendar_view=calendar_view, field=field
        )
