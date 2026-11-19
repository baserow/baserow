from django.db import migrations, models

from baserow.core.migration_utils import RetryableAddIndexConcurrently


class Migration(migrations.Migration):
    # The indexes are built without blocking the comments written meanwhile.
    atomic = False

    dependencies = [
        ("baserow_premium", "0033_aggregation_group_by_mode"),
    ]

    operations = [
        RetryableAddIndexConcurrently(
            model_name="rowcomment",
            index=models.Index(
                fields=["table", "-created_on"], name="rowcomment_table_created_idx"
            ),
        ),
        RetryableAddIndexConcurrently(
            model_name="rowcomment",
            index=models.Index(
                fields=["table", "user", "-created_on"],
                name="rowcomment_table_author_idx",
            ),
        ),
    ]
