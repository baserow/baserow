import pytest
from freezegun import freeze_time

from baserow.core.import_export.handler import ImportApplicationsJob
from baserow.core.import_export.tasks import (
    delete_marked_import_export_resources,
    mark_import_export_resources_for_deletion,
)
from baserow.core.models import ExportApplicationsJob, ImportExportResource


@pytest.mark.django_db
def test_mark_import_export_resources_for_deletion(data_fixture):
    with freeze_time("2021-01-01 12:00"):
        resource_1 = data_fixture.create_import_export_resource(is_valid=True)

    with freeze_time("2021-01-05 12:00"):
        resource_2 = data_fixture.create_import_export_resource(is_valid=False)
        resource_3 = data_fixture.create_import_export_resource(is_valid=True)

        mark_import_export_resources_for_deletion(older_than_days=3)

    resource_1.refresh_from_db()
    resource_2.refresh_from_db()
    resource_3.refresh_from_db()

    assert resource_1.marked_for_deletion is True
    assert resource_2.marked_for_deletion is True
    assert resource_3.marked_for_deletion is False  # Valid and not older than 3 days


@pytest.mark.django_db
def test_delete_marked_import_export_resources(data_fixture):
    resource_1 = data_fixture.create_import_export_resource(
        is_valid=True, marked_for_deletion=True
    )
    resource_2 = data_fixture.create_import_export_resource(
        is_valid=False, marked_for_deletion=True
    )
    resource_3 = data_fixture.create_import_export_resource(
        is_valid=True, marked_for_deletion=False
    )

    delete_marked_import_export_resources()

    remaining_resources = ImportExportResource.objects.filter().values_list(
        "id", flat=True
    )
    assert list(remaining_resources) == [resource_3.id]


@pytest.mark.django_db
def test_resources_in_use_wont_be_deleted(data_fixture):
    user = data_fixture.create_user()

    with freeze_time("2021-01-05 12:00"):
        export_resource = data_fixture.create_import_export_resource(is_valid=True)
        export_job = ExportApplicationsJob.objects.create(
            user=user, resource=export_resource, state="running"
        )
        export_resource_2 = data_fixture.create_import_export_resource(is_valid=True)
        ExportApplicationsJob.objects.create(
            user=user, resource=export_resource_2, state="running"
        )

        import_resource = data_fixture.create_import_export_resource(is_valid=True)
        import_job = ImportApplicationsJob.objects.create(
            user=user, resource=import_resource, state="running"
        )
        import_resource_2 = data_fixture.create_import_export_resource(is_valid=True)
        ImportApplicationsJob.objects.create(
            user=user, resource=import_resource_2, state="running"
        )

    with freeze_time("2021-01-06 12:05"):
        mark_import_export_resources_for_deletion(older_than_days=1)
        delete_marked_import_export_resources()

    assert ImportExportResource.objects_and_trash.filter().count() == 4

    export_job.state = "finished"
    export_job.save()
    import_job.state = "failed"
    import_job.save()

    # Only the resources that are not in use should be deleted.
    with freeze_time("2021-01-06 12:10"):
        delete_marked_import_export_resources()

    assert ImportExportResource.objects_and_trash.filter().count() == 2

    # After 3 days also the remaining resources should be deleted.
    with freeze_time("2021-01-08 12:05"):
        delete_marked_import_export_resources()

    assert ImportExportResource.objects_and_trash.filter().count() == 0
