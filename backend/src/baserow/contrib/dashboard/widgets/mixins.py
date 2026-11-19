from copy import deepcopy

from baserow.core.feature_flags import FF_DASHBOARD_FILTERS, feature_flag_is_enabled


class DisplayWidgetTypeMixin:
    """Identify widgets whose data source can receive contributed filter groups."""

    is_display_widget = True

    def get_data_source(self, widget):
        return widget.data_source

    def after_update(self, updated_widget, **kwargs):
        """
        Clear old-table conditions when data_source is among the updated fields.
        Keep links and collect original conditions for undo and notifications.
        """
        from baserow.contrib.dashboard.widgets.handler import WidgetHandler
        from baserow.contrib.dashboard.widgets.models import Widget

        updated_widget = super().after_update(updated_widget, **kwargs)
        if "data_source" not in updated_widget.new_values:
            return updated_widget
        instance = updated_widget.widget
        updated_data_source = updated_widget.new_values["data_source"]
        original_table_id = updated_widget.original_values["data_source"]["table_id"]
        source = self.get_data_source(instance)
        if (
            source is None
            or source.id != updated_data_source.data_source.id
            or original_table_id == getattr(source.service.specific, "table_id", None)
        ):
            return updated_widget

        for widget in WidgetHandler().get_widgets_for_update(
            instance.dashboard, base_queryset=Widget.objects_and_trash.all()
        ):
            widget = widget.specific
            filter_type = widget.get_type()
            if not filter_type.is_filter_widget:
                continue
            links = filter_type.get_target_filters(widget)
            updated = deepcopy(links)
            originals = []
            for link, replacement in zip(links, updated):
                if link["target_widget_id"] != instance.id:
                    continue
                replacement["group"] = {
                    "filter_type": "AND",
                    "filters": [],
                    "filter_groups": [],
                }
                replacement["empty_behavior"] = "apply_nothing"
                replacement.pop("alternative_group", None)
                if link != replacement:
                    originals.append(link)
            if originals:
                updated_data_source.original_filter_links.setdefault(
                    str(widget.id), []
                ).extend(originals)
                filter_type.set_target_filters(widget, updated)
                # A filter can target several displays sharing the same source.
                changed = updated_data_source.updated_filter_widgets
                changed[:] = [
                    existing for existing in changed if existing.id != widget.id
                ]
                changed.append(widget)

        return updated_widget

    def before_trashed(self, instance, requesting_user, trash_entry):
        """Snapshot and remove filter links before trashing the display's source."""
        from baserow.contrib.dashboard.widgets.handler import WidgetHandler
        from baserow.contrib.dashboard.widgets.models import Widget
        from baserow.contrib.dashboard.widgets.signals import widget_updated

        links = {}
        # Trashed filters can be restored before this target, so clean their links too.
        for widget in WidgetHandler().get_widgets_for_update(
            instance.dashboard, base_queryset=Widget.objects_and_trash.all()
        ):
            widget = widget.specific
            filter_type = widget.get_type()
            if not filter_type.is_filter_widget:
                continue
            configured = filter_type.get_target_filters(widget)
            removed = [
                link for link in configured if link["target_widget_id"] == instance.id
            ]
            if removed:
                links[str(widget.id)] = removed
                filter_type.set_target_filters(
                    widget,
                    [
                        link
                        for link in configured
                        if link["target_widget_id"] != instance.id
                    ],
                )
                if not widget.trashed:
                    widget_updated.send(self, widget=widget, user=requesting_user)
        trash_entry.additional_restoration_data = {
            **(trash_entry.additional_restoration_data or {}),
            "target_links": links,
        }
        trash_entry.save(update_fields=["additional_restoration_data"])
        source = self.get_data_source(instance)
        source.trashed = True
        source.save(update_fields=["trashed"])
        super().before_trashed(instance, requesting_user, trash_entry)

    def before_restore(self, instance, trash_entry):
        """Restore the display's data source before the widget becomes active."""
        source = self.get_data_source(instance)
        source.trashed = False
        source.save(update_fields=["trashed"])
        super().before_restore(instance, trash_entry)

    def after_restore(self, instance, trash_entry):
        """Recover links for active or trashed owners without replacing new links."""
        from baserow.contrib.dashboard.widgets.models import Widget
        from baserow.contrib.dashboard.widgets.signals import widget_updated

        for widget_id, links in (
            (trash_entry.additional_restoration_data or {})
            .get("target_links", {})
            .items()
        ):
            widget = (
                Widget.objects_and_trash.select_for_update()
                .filter(id=widget_id, dashboard_id=instance.dashboard_id)
                .first()
            )
            if widget is None:
                continue
            widget = widget.specific
            filter_type = widget.get_type()
            if not filter_type.is_filter_widget:
                continue
            configured = filter_type.get_target_filters(widget)
            existing = {link["target_widget_id"] for link in configured}
            filter_type.set_target_filters(
                widget,
                [
                    *configured,
                    *[
                        link
                        for link in links
                        if link["target_widget_id"] not in existing
                    ],
                ],
            )
            if not widget.trashed:
                widget_updated.send(self, widget=widget, user=None)
        super().after_restore(instance, trash_entry)


class FilterWidgetTypeMixin:
    """Shared explicit links and lifecycle operations for dashboard filter types."""

    is_filter_widget = True
    public_serializer_field_names = ["target_widget_ids"]

    def before_create(self, user, dashboard):
        feature_flag_is_enabled(FF_DASHBOARD_FILTERS, raise_if_disabled=True)
        return super().before_create(user, dashboard)

    @property
    def public_serializer_mixins(self):
        from baserow.contrib.dashboard.api.widgets.serializers import (
            FilterWidgetPublicSerializerMixin,
        )

        return [FilterWidgetPublicSerializerMixin]

    def enhance_queryset(self, queryset):
        return (
            super()
            .enhance_queryset(queryset)
            .prefetch_related("filter_targets__groups__conditions")
        )

    def validate_target_filters(self, links, dashboard_id):
        """Validate explicit links before persisting either API or internal changes."""
        from rest_framework.exceptions import ValidationError

        from baserow.contrib.dashboard.widgets.models import Widget
        from baserow.contrib.integrations.local_baserow.service_filter_groups import (
            get_deleted_field_ids,
            validate_runtime_filter_group,
        )

        if not isinstance(links, list):
            raise ValidationError("Target filters must be a list.")
        known = set()
        for link in links:
            if not isinstance(link, dict) or not isinstance(
                link.get("target_widget_id"), int
            ):
                raise ValidationError("Invalid target widget.")
            if not isinstance(link.get("enabled", True), bool):
                raise ValidationError("Target filter enabled must be a boolean.")
            target_id = link["target_widget_id"]
            if target_id in known:
                raise ValidationError("Duplicate target widget.")
            known.add(target_id)
            target = Widget.objects.filter(
                id=target_id, dashboard_id=dashboard_id
            ).first()
            target = target.specific if target else None
            target_type = target.get_type() if target else None
            source = (
                target_type.get_data_source(target)
                if target_type and target_type.is_display_widget
                else None
            )
            if source is None or not source.service_id:
                raise ValidationError(
                    "The target must have a filterable data source in this dashboard."
                )
            service = source.service.specific
            if not hasattr(service, "service_filters") or not service.table_id:
                raise ValidationError("The target has no filterable source.")
            behavior = link.get("empty_behavior", "apply_nothing")
            if behavior not in ("apply_nothing", "apply_alternative"):
                raise ValidationError("Invalid empty input behavior.")
            keys = ["group"]
            if (
                behavior == "apply_alternative"
                or link.get("alternative_group") is not None
            ):
                keys.append("alternative_group")
            for key in keys:
                filters, _ = validate_runtime_filter_group(link.get(key), service)
                originals = link[key].get("filters", [])
                for condition in filters:
                    originals[condition["index"]]["value"] = condition["value"]
                # Conditions on deleted fields stay, inactive, like imported ones.
                validated = {condition["index"] for condition in filters}
                deleted = get_deleted_field_ids(
                    condition["field"]
                    for index, condition in enumerate(originals)
                    if index not in validated
                )
                for condition in originals:
                    if condition["field"] in deleted:
                        condition["field"] = 0

    def prepare_value_for_db(self, values, instance=None):
        """Validate contributed groups for every filter type using this mixin."""
        if "target_filters" in values:
            self.validate_target_filters(
                values["target_filters"],
                instance.dashboard_id if instance else values["dashboard"].id,
            )
        return super().prepare_value_for_db(values, instance)

    def after_data_source_restore(
        self, instance, updated_data_source, restoration_data
    ):
        """Restore saved target links while preserving other current conditions."""
        changed = super().after_data_source_restore(
            instance, updated_data_source, restoration_data
        )
        if "target_filters" not in restoration_data:
            return changed
        replacements = {
            link["target_widget_id"]: link
            for link in restoration_data["target_filters"]
        }
        self.set_target_filters(
            instance,
            [
                replacements.get(link["target_widget_id"], link)
                for link in self.get_target_filters(instance)
            ],
        )

        return True

    def formula_generator(self, instance):
        """Include both branches of each target's contributed condition formulas."""
        yield from super().formula_generator(instance)
        for link in self.get_target_filters(instance):
            for key in ("group", "alternative_group"):
                for condition in (link.get(key) or {}).get("filters", []):
                    new_formula = yield condition.get("value", "")
                    if new_formula is not None:
                        condition["value"] = new_formula
                        yield instance

    def get_target_filters(self, widget):
        return widget.target_filters

    def set_target_filters(self, widget, links):
        widget.target_filters = links
        widget.save(update_fields=["target_filters"])

    def get_runtime_filter(self, widget, target, dispatch_context):
        """Select a group using the owning filter's value and empty-input policy."""
        for link in self.get_target_filters(widget):
            if link["target_widget_id"] != target.id or not link.get("enabled", True):
                continue
            value = dispatch_context[f"widget_data.{widget.id}"]
            if value != "" and value != []:
                return link["group"]
            if link.get("empty_behavior") == "apply_alternative":
                return link["alternative_group"]
        return None

    def create_instance_from_serialized(self, serialized_values, **kwargs):
        """Defer filter links until all imported widget IDs can be remapped."""
        links = serialized_values.pop("target_filters", [])
        widget = super().create_instance_from_serialized(serialized_values, **kwargs)
        widget.target_filters = links
        return widget

    def after_import(self, widget, id_mapping, **kwargs):
        """Remap target IDs, fields and formulas after all widgets are imported."""
        from baserow.contrib.dashboard.formula_importer import import_formula
        from baserow.contrib.dashboard.widgets.models import Widget
        from baserow.core.services.registries import service_type_registry

        updated_models = super().after_import(widget, id_mapping, **kwargs)
        import_export_config = kwargs.get("import_export_config")
        imported_links = []
        for link in self.get_target_filters(widget):
            target_id = id_mapping.get("dashboard_widgets", {}).get(
                link["target_widget_id"]
            )
            target = Widget.objects.filter(id=target_id).first() if target_id else None
            target = target.specific if target else None
            source = target.get_type().get_data_source(target) if target else None
            if source is None or not source.service_id:
                # The export doesn't contain the target or its source anymore, so
                # the link can't apply. Drop it rather than failing the import.
                continue
            link["target_widget_id"] = target_id
            imported_links.append(link)
            service_type = service_type_registry.get_by_model(
                source.service.specific_class
            )
            for key in ("group", "alternative_group"):
                group = link.get(key)
                if group is None:
                    continue
                for condition in group["filters"]:
                    original = {**condition, "field_id": condition["field"]}
                    remapped = service_type.deserialize_filters(
                        [original], id_mapping, import_export_config
                    )
                    if remapped:
                        condition["field"] = remapped[0]["field_id"]
                        condition["value"] = import_formula(
                            remapped[0]["value"], id_mapping
                        )
                    else:
                        # The condition stays, inactive, until edited, but its
                        # widget references must still point at the imported copy.
                        condition["field"] = 0
                        condition["value"] = import_formula(
                            condition["value"], id_mapping
                        )
        # Saved with the other imported changes of the widget.
        widget.target_filters = imported_links
        updated_models.add(widget)
        return updated_models
