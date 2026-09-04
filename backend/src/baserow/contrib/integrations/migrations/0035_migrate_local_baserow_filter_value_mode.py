from django.db import migrations, transaction

from baserow.core.utils import Progress, grouper


BATCH_SIZE = 1000


def migrate_filter_values_to_raw_mode(apps, schema_editor):
    """
    Migrates legacy non-formula filter values to raw mode in short transactions.
    """

    LocalBaserowTableServiceFilter = apps.get_model(
        "integrations", "LocalBaserowTableServiceFilter"
    )

    # Materialize the IDs instead of using .iterator(), which would keep a
    # server-side cursor and its implicit transaction open for the whole migration.
    filter_ids = list(
        LocalBaserowTableServiceFilter.objects.filter(value_is_formula=False)
        .values_list("id", flat=True)
        .order_by("id")
    )

    progress = Progress(len(filter_ids))
    progress.register_updated_event(
        lambda pct, _: print(
            f"\r  Migrating Local Baserow filters... {pct}%",
            end="",
            flush=True,
        )
    )

    for chunk_ids in grouper(BATCH_SIZE, iter(filter_ids)):
        chunk_ids = list(chunk_ids)
        with transaction.atomic():
            filters_to_update = []
            for service_filter in LocalBaserowTableServiceFilter.objects.filter(
                id__in=chunk_ids
            ):
                value = service_filter.value
                if isinstance(value, dict):
                    value["mode"] = "raw"
                else:
                    value = {
                        "formula": "" if value is None else str(value),
                        "mode": "raw",
                        "version": "0.1",
                    }

                service_filter.value = value
                filters_to_update.append(service_filter)

            LocalBaserowTableServiceFilter.objects.bulk_update(
                filters_to_update, ["value"]
            )

        progress.increment(by=len(chunk_ids))

    print()


class Migration(migrations.Migration):
    # Each batch must be able to commit independently so updated rows aren't locked
    # for the full duration of the data migration.
    atomic = False

    dependencies = [
        ("integrations", "0034_coreresponseservice_and_more"),
    ]

    operations = [
        migrations.RunPython(
            migrate_filter_values_to_raw_mode, migrations.RunPython.noop
        ),
    ]
