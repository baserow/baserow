from datetime import datetime, timezone
from typing import Optional

from django.db.models import F, OuterRef, PositiveIntegerField, Subquery, Sum
from django.db.models.functions import Coalesce

from baserow.core.models import Workspace
from baserow.core.usage.registries import workspace_storage_usage_item_registry
from baserow.core.utils import ChildProgressBuilder, grouper


class UsageHandler:
    @classmethod
    def calculate_storage_usage(
        cls,
        progress_builder: Optional[ChildProgressBuilder] = None,
    ) -> int:
        """
        Calculates the storage usage of every workspace.

        :param progress_builder: An optional progress builder that can be used to
            indicate the progress of the calculation.
        :return: The amount of workspaces that have been updated.
        """

        count, chunk_size = 0, 256
        qs = Workspace.objects.filter(template__isnull=True)
        workspaces_queryset = qs.iterator(chunk_size=chunk_size)

        progress = ChildProgressBuilder.build(progress_builder, child_total=qs.count())

        for item in workspace_storage_usage_item_registry.get_all():
            item.calculate_storage_usage_instance()

        for workspaces in grouper(chunk_size, workspaces_queryset):
            now = datetime.now(tz=timezone.utc)
            for workspace in workspaces:
                usage_in_megabytes = 0
                for item in workspace_storage_usage_item_registry.get_all():
                    usage_in_megabytes += item.calculate_storage_usage_workspace(
                        workspace.id
                    )

                workspace.storage_usage = usage_in_megabytes
                workspace.storage_usage_updated_at = now
                progress.increment()

            Workspace.objects.bulk_update(
                workspaces, ["storage_usage", "storage_usage_updated_at"]
            )
            count += len(workspaces)

        return count

    @classmethod
    def get_workspace_row_count_annotation(cls, outer_ref_name: str = "id") -> Coalesce:
        """
        Generates a subquery that can be used to count the row_count on a Workspace
        QuerySet.

        :param outer_ref_name: The name of the outer ref used to identify the workspace
            name.
        :return: The generated SubQuery.
        """

        # FIXME: Move this to baserow.contrib.database
        from baserow.contrib.database.table.models import Table, TableUsageUpdate

        return Coalesce(
            Subquery(
                Table.objects.filter(
                    database__workspace_id=OuterRef(outer_ref_name),
                    database__trashed=False,
                )
                .annotate(row_usage_count=Coalesce("usage__row_count", 0))
                .annotate(
                    row_update_count=Subquery(
                        TableUsageUpdate.objects.filter(
                            table_id=OuterRef("id"),
                            row_count__isnull=False,
                        )
                        .values("table_id")
                        .annotate(row_count=Coalesce(Sum("row_count"), 0))
                        .values("row_count")[:1]
                    )
                )
                .annotate(
                    row_count=F("row_usage_count") + Coalesce(F("row_update_count"), 0)
                )
                .values("database__workspace_id")
                .annotate(total=Sum("row_count"))
                .values("total"),
                output_field=PositiveIntegerField(),
            ),
            0,
        )
