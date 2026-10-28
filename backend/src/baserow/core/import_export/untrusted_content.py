from baserow.core.deferred_callbacks import register_deferred_callback


class UntrustedContentTypeMixin:
    """Marks active content in the cache belonging to one content owner copy."""

    def export_serialized(self, *args, **kwargs):
        if (cache := kwargs.get("cache")) is not None:
            cache["has_untrusted_content"] = True
        return super().export_serialized(*args, **kwargs)

    def import_serialized(
        self,
        parent,
        serialized_values,
        id_mapping,
        files_zip=None,
        storage=None,
        cache=None,
        **kwargs,
    ):
        """Import active content and record its new IDs in the owner's report cache."""

        instance = super().import_serialized(
            parent,
            serialized_values,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )
        if cache is not None:
            cache.setdefault("import_report", []).append(
                self.get_import_report_entry(instance)
            )
        return instance

    def get_import_report_entry(self, instance):
        """Describe the imported active content without copying executable code."""

        raise NotImplementedError


def defer_untrusted_content_update(content_owner, cache, import_export_config):
    """Persist the import report and finalize external content restrictions.

    The closure retains this content owner's cache even when other content owners are
    imported before deferred callbacks run. Update the returned model instance too,
    so API responses and subsequent publication see the persisted restriction.
    """

    external = not (
        import_export_config.is_duplicate
        or import_export_config.is_publishing
        or import_export_config.is_template
    )

    def update_untrusted_content():
        content_owner.import_report = cache.get("import_report", [])
        update_fields = ["import_report"]
        if external:
            content_owner.untrusted_content = bool(content_owner.import_report)
            update_fields.append("untrusted_content")
        content_owner.save(update_fields=update_fields)

    register_deferred_callback(update_untrusted_content)
