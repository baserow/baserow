from django.db.models import QuerySet

from baserow.core.models import Workspace
from baserow.core.registries import subject_type_registry


class SubjectOptionsHandler:
    """Builds searchable subject option querysets from registered subject types."""

    @classmethod
    def get_options(
        cls,
        workspace: Workspace | None = None,
        search: str = "",
        subject_types: set[str] | None = None,
        exclude_ids: dict[str, list[int]] | None = None,
    ) -> QuerySet:
        """Return a unified queryset supplied by listable subject types.

        Permission checks remain with the caller because consumers expose subject
        options under different capabilities.
        """

        search = (search or "").strip()
        exclude_ids = exclude_ids or {}
        requested_types = subject_types or set(subject_type_registry.get_types())
        option_querysets = []
        for subject_type in subject_type_registry.get_all():
            if subject_type.type not in requested_types:
                continue
            queryset = subject_type.get_options_queryset(
                workspace=workspace,
                search=search,
                exclude_ids=exclude_ids.get(subject_type.type, []),
            )
            if queryset is not None:
                option_querysets.append(queryset)

        if not option_querysets:
            raise ValueError("No listable subject types were requested.")

        queryset = option_querysets[0]
        for option_queryset in option_querysets[1:]:
            queryset = queryset.union(option_queryset, all=True)
        return queryset.order_by("subject_label", "subject_type", "subject_id")
