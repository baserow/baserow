class DisplayWidgetTypeMixin:
    """Identify widgets whose data source can receive contributed filter groups."""

    is_display_widget = True

    def get_data_source(self, widget):
        return widget.data_source

    def after_import(self, widget, id_mapping, **kwargs):
        """Finalize the display's source once, even when widgets share that source."""
        from baserow.contrib.dashboard.formula_importer import import_formula

        updated_models = super().after_import(widget, id_mapping, **kwargs)
        source = self.get_data_source(widget)
        finalized_sources = kwargs.get("import_context", {}).setdefault(
            "data_source_ids", set()
        )
        if (
            source is not None
            and source.service_id
            and source.id not in finalized_sources
        ):
            service = source.service.specific
            updated_models.update(
                service.get_type().after_import(
                    service, id_mapping, **{**kwargs, "import_formula": import_formula}
                )
            )
            finalized_sources.add(source.id)
        return updated_models

    def before_trashed(self, instance, requesting_user, trash_entry):
        """Snapshot and remove filter links before trashing the display's source."""
        from baserow.contrib.dashboard.widgets.handler import WidgetHandler
        from baserow.contrib.dashboard.widgets.signals import widget_updated

        links = {}
        for widget in WidgetHandler().get_widgets_for_update(instance.dashboard):
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
        """Recover saved links for active filter owners without replacing new links."""
        from baserow.contrib.dashboard.widgets.models import Widget
        from baserow.contrib.dashboard.widgets.signals import widget_updated

        for widget_id, links in (
            (trash_entry.additional_restoration_data or {})
            .get("target_links", {})
            .items()
        ):
            widget = (
                Widget.objects.select_for_update()
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
            widget_updated.send(self, widget=widget, user=None)
        super().after_restore(instance, trash_entry)


class FilterWidgetTypeMixin:
    """Shared explicit links and lifecycle operations for dashboard filter types."""

    is_filter_widget = True
    public_serializer_field_names = ["target_widget_ids"]

    @property
    def public_serializer_mixins(self):
        from baserow.contrib.dashboard.api.widgets.serializers import (
            FilterWidgetPublicSerializerMixin,
        )

        return [FilterWidgetPublicSerializerMixin]

    def validate_target_filters(self, links, dashboard_id):
        """Validate explicit links before persisting either API or internal changes."""
        from rest_framework.exceptions import ValidationError

        from baserow.contrib.dashboard.widgets.models import Widget
        from baserow.contrib.integrations.local_baserow.service_filter_groups import (
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
                for condition, original in zip(filters, link[key].get("filters", [])):
                    original["value"] = condition["value"]

    def prepare_value_for_db(self, values, instance=None):
        """Validate contributed groups for every filter type using this mixin."""
        if "target_filters" in values:
            self.validate_target_filters(
                values["target_filters"],
                instance.dashboard_id if instance else values["dashboard"].id,
            )
        return super().prepare_value_for_db(values, instance)

    def get_target_filters(self, widget):
        return widget.target_filters

    def set_target_filters(self, widget, links):
        widget.target_filters = links
        widget.save(update_fields=["target_filters"])

    def get_filter_value(self, widget, values):
        """Resolve a viewer value, falling back to this filter type's default."""
        raise NotImplementedError()

    def validate_filter_value(self, widget, value):
        """Validate viewer data according to this filter type's value contract."""
        raise NotImplementedError()

    def get_runtime_filter(self, widget, target, dispatch_context):
        """Select a group using the owning filter's value and empty-input policy."""
        value = dispatch_context[f"widget_data.{widget.id}"]
        for link in self.get_target_filters(widget):
            if link["target_widget_id"] != target.id:
                continue
            if value != "":
                return link["group"]
            if link.get("empty_behavior") == "apply_alternative":
                return link["alternative_group"]
        return None

    def after_import(self, widget, id_mapping, **kwargs):
        """Remap target IDs, fields and formulas after all widgets are imported."""
        from baserow.contrib.dashboard.formula_importer import import_formula
        from baserow.contrib.dashboard.widgets.models import Widget
        from baserow.core.services.registries import service_type_registry

        updated_models = super().after_import(widget, id_mapping, **kwargs)
        import_export_config = kwargs.get("import_export_config")
        for link in self.get_target_filters(widget):
            link["target_widget_id"] = id_mapping["dashboard_widgets"][
                link["target_widget_id"]
            ]
            target = Widget.objects.get(id=link["target_widget_id"]).specific
            source = target.get_type().get_data_source(target)
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
                        condition["field"] = 0
        updated_models.add(widget)
        return updated_models
