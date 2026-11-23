from django.db import migrations, models
from django.db.models import Count, OuterRef, Subquery


def set_max_snapshots_of_applications_with_snapshots(apps, schema_editor):
    """
    Every existing snapshot is protected, and a max can't be lower than the number of
    protected snapshots an application holds. The workspace default max snapshots starts
    at 0, so the applications that already hold snapshots get a max of their own, equal
    to the number they hold.
    """

    Application = apps.get_model("core", "Application")
    Snapshot = apps.get_model("core", "Snapshot")

    restorable = Snapshot.objects.filter(
        snapshot_to_application__isnull=False, mark_for_deletion=False
    )
    counts = (
        restorable.filter(snapshot_from_application_id=OuterRef("id"))
        .order_by()
        .values("snapshot_from_application_id")
        .annotate(count=Count("id"))
        .values("count")
    )
    Application.objects.filter(
        id__in=restorable.values("snapshot_from_application_id"),
        max_snapshots__isnull=True,
    ).update(max_snapshots=Subquery(counts))


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0141_ai_provider_excluded_workspaces"),
    ]

    operations = [
        migrations.AddField(
            model_name="snapshot",
            name="created_automatically",
            field=models.BooleanField(
                db_default=False,
                default=False,
                help_text=(
                    "Indicates that the snapshot was created by an automatic "
                    "snapshot schedule instead of by a user."
                ),
            ),
        ),
        migrations.AddField(
            model_name="snapshot",
            name="protected",
            field=models.BooleanField(
                db_default=True,
                default=True,
                help_text=(
                    "A protected snapshot is never deleted automatically to make room "
                    "for a new one or when a max is lowered. It still expires."
                ),
            ),
        ),
        migrations.AddField(
            model_name="workspace",
            name="default_max_snapshots",
            field=models.PositiveIntegerField(
                db_default=0,
                default=0,
                help_text=(
                    "How many snapshots each application of the workspace keeps when "
                    "it doesn't have a max of its own. Every max reserves that many "
                    "snapshots of the workspace's snapshot allowance."
                ),
            ),
        ),
        migrations.AddField(
            model_name="application",
            name="max_snapshots",
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                help_text=(
                    "How many snapshots the application keeps. Empty to follow the "
                    "workspace default max snapshots."
                ),
            ),
        ),
        migrations.RunPython(
            set_max_snapshots_of_applications_with_snapshots,
            migrations.RunPython.noop,
        ),
    ]
