from django.core.management import BaseCommand

from baserow.contrib.automation.nodes.backfill import (
    BACKFILL_DONE_CACHE_KEY,
    fill_missing_table_ids,
)


class Command(BaseCommand):
    help = (
        "Fills the tables the test run data and run history of automations were "
        "built from, where they are missing. Safe to run again."
    )

    def handle(self, *args, **options):
        from django.core.cache import cache

        # Looks again, even when a previous pass marked the fill done.
        cache.delete(BACKFILL_DONE_CACHE_KEY)
        if fill_missing_table_ids():
            self.stdout.write("All table IDs are filled.")
        else:
            self.stdout.write(
                "Some workflows couldn't be filled, see the log. Run it again."
            )
