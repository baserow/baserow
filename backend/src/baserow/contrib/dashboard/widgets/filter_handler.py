from copy import deepcopy

from baserow.core.services.filter_groups import (
    replace_filters,
    serialize_filter,
    serialize_filter_group,
    sync_filter_groups,
)

from .models import WidgetFilterCondition, WidgetFilterGroup, WidgetFilterTarget

# The optional API attributes kept in each level's `configuration`, so that a
# configuration reads back exactly as it was written. Anything else is dropped.
LINK_CONFIGURATION_KEYS = ("enabled", "empty_behavior")
CONDITION_CONFIGURATION_KEYS = ("id", "group")


def pick(values: dict, keys) -> dict:
    return {key: values[key] for key in keys if key in values}


class WidgetFilterHandler:
    """Translate the stable filter API representation into relational records."""

    def get_target_filters(self, widget):
        """Load all branches in three queries, preserving client group identifiers."""
        if not widget.pk:
            return []
        links = []
        targets = widget.filter_targets.all()
        if "filter_targets" not in getattr(widget, "_prefetched_objects_cache", {}):
            targets = targets.prefetch_related("groups__conditions")
        for target in targets:
            link = {**target.configuration, "target_widget_id": target.target_widget_id}
            if target.enabled is not True or "enabled" in link:
                link["enabled"] = target.enabled
            if target.empty_behavior != "apply_nothing" or "empty_behavior" in link:
                link["empty_behavior"] = target.empty_behavior
            groups = list(target.groups.all())
            for root in [group for group in groups if group.parent_group_id is None]:
                branch = "alternative_group" if root.alternative else "group"
                children = [
                    g
                    for g in groups
                    if g.alternative == root.alternative
                    and g.parent_group_id is not None
                ]
                group_by_id = {g.id: g for g in groups}
                result = {
                    **root.configuration,
                    "filter_type": root.filter_type,
                    "filters": [],
                    "filter_groups": [],
                }
                for child in children:
                    parent = group_by_id[child.parent_group_id]
                    result["filter_groups"].append(
                        serialize_filter_group(
                            child,
                            reference=child.reference,
                            parent_reference=parent.reference,
                            extra=child.configuration,
                        )
                    )
                conditions = [
                    (g, c) for g in [root, *children] for c in g.conditions.all()
                ]
                for group, condition in sorted(
                    conditions, key=lambda item: item[1].order
                ):
                    result["filters"].append(
                        serialize_filter(
                            condition,
                            field_key="field",
                            group_id=group.reference,
                            include_group=group.id != root.id
                            or "group" in condition.configuration,
                            extra=condition.configuration,
                        )
                    )
                link[branch] = result
            links.append(link)
        return links

    def set_target_filters(self, widget, links):
        """Replace a validated configuration, with cascading group/condition cleanup.

        The caller owns the transaction, just as for widget updates. Import calls
        this only after target widget and integration field mappings are available.
        """
        links = deepcopy(links)
        widget.filter_targets.all().delete()
        for order, link in enumerate(links):
            target = WidgetFilterTarget.objects.create(
                widget=widget,
                target_widget_id=link["target_widget_id"],
                order=order,
                enabled=link.get("enabled", True),
                empty_behavior=link.get("empty_behavior", "apply_nothing"),
                configuration=pick(link, LINK_CONFIGURATION_KEYS),
            )
            for branch in ("group", "alternative_group"):
                configuration = link.get(branch)
                if configuration is None:
                    continue
                self._create_branch(
                    target, configuration, branch == "alternative_group"
                )
        widget._prefetched_objects_cache = {}
        # Read back what was stored, so callers see the normalized configuration.
        widget._target_filters = self.get_target_filters(widget)
        from baserow.contrib.dashboard.receivers import (
            invalidate_changed_widget_properties,
        )

        invalidate_changed_widget_properties(type(widget), widget)

    def _create_branch(self, target, configuration, alternative):
        """Create a branch root, resolve nested group references, then its formulas."""
        root = WidgetFilterGroup.objects.create(
            target=target,
            alternative=alternative,
            filter_type=configuration.get("filter_type", "AND"),
        )
        groups = sync_filter_groups(
            WidgetFilterGroup.objects.none(),
            [
                {
                    "id": group["id"],
                    "parent_group_id": group.get("parent_group"),
                    "reference": group["id"],
                    "filter_type": group.get("filter_type", "AND"),
                    "order": index,
                }
                for index, group in enumerate(configuration.get("filter_groups", []))
            ],
            owner_values={"target": target, "alternative": alternative},
            root=root,
        )
        conditions = []
        value_field = WidgetFilterCondition._meta.get_field("value")
        for condition in configuration.get("filters", []):
            condition["value"] = value_field.to_python(condition.get("value", ""))
            conditions.append(
                {
                    "field_id": condition["field"],
                    "type": condition["type"],
                    "value": condition["value"],
                    "group_id": condition.get("group"),
                    "configuration": pick(condition, CONDITION_CONFIGURATION_KEYS),
                }
            )
        replace_filters(
            WidgetFilterCondition.objects.none(),
            conditions,
            groups=groups,
            owner_values={},
            root=root,
        )
