from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.builder.models import Builder
from baserow_enterprise.builder.custom_code.models import BuilderCustomScript
from baserow_enterprise.builder.custom_code.types import BuilderCustomCodeDict
from baserow_enterprise.features import BUILDER_CUSTOM_CODE


class CustomCodeBuilderApplicationTypeMixin:
    @property
    def serializer_field_names(self):
        return super().serializer_field_names + [
            "scripts",
            "custom_code",
        ]

    @property
    def public_serializer_field_names(self):
        return super().public_serializer_field_names + [
            "scripts",
            "custom_code",
        ]

    @property
    def request_serializer_field_names(self):
        return super().request_serializer_field_names + [
            "scripts",
            "custom_code",
        ]

    @property
    def serializer_mixins(self):
        from baserow_enterprise.api.builder.custom_code.serializers import (
            EnterpriseBuilderCustomCodeSerializer,
        )

        return super().serializer_mixins + [EnterpriseBuilderCustomCodeSerializer]

    @property
    def public_serializer_mixins(self):
        from baserow_enterprise.api.builder.custom_code.serializers import (
            EnterpriseBuilderCustomCodeSerializer,
        )

        return super().public_serializer_mixins + [
            EnterpriseBuilderCustomCodeSerializer
        ]

    @property
    def serializer_field_overrides(self):
        from baserow_enterprise.api.builder.custom_code.serializers import (
            CustomCodeSerializer,
        )

        return {
            **super().serializer_field_overrides,
            "custom_code": CustomCodeSerializer(
                help_text="Custom CSS/JS code for this builder"
            ),
        }

    @property
    def request_serializer_field_overrides(self):
        from baserow_enterprise.api.builder.custom_code.serializers import (
            CustomCodeSerializer,
            CustomScriptSerializer,
        )

        return {
            **super().serializer_field_overrides,
            "scripts": CustomScriptSerializer(
                help_text="Custom CSS/JS scripts for this builder",
                many=True,
                required=False,
            ),
            "custom_code": CustomCodeSerializer(
                help_text="Custom CSS/JS code for this builder", required=False
            ),
        }

    def _create_scripts_in_bulk(self, instance, scripts):
        bulk = []
        for order, fdata in enumerate(scripts):
            fdata.pop("id", None)
            bulk.append(BuilderCustomScript(builder=instance, order=order, **fdata))

        BuilderCustomScript.objects.bulk_create(bulk)

    def _update_scripts_and_custom_code(self, instance, values):
        """
        Handles custom code and scripts.
        """

        # We don't want to update the content if we don't have the licence
        if not LicenseHandler.workspace_has_feature(
            BUILDER_CUSTOM_CODE, instance.get_workspace()
        ):
            return

        if "scripts" in values:
            # Bulk delete the existing ones on the builder.
            instance.scripts.all().delete()

            self._create_scripts_in_bulk(instance, values["scripts"])

        if "custom_code" in values:
            instance.custom_code.css = values["custom_code"].get("css", "")
            instance.custom_code.js = values["custom_code"].get("js", "")
            instance.custom_code.save()

    def after_update(self, instance, values):
        """
        Handles custom code and scripts.
        """

        super().after_update(instance, values)

        self._update_scripts_and_custom_code(instance, values)

    def after_create(
        self,
        instance,
        values,
    ):
        """
        Handles custom code and scripts.
        """

        super().after_create(instance, values)

        self._update_scripts_and_custom_code(instance, values)

    def _get_base_enhanced_queryset(self, queryset):
        enhanced_queryset = super()._get_base_enhanced_queryset(queryset)
        return enhanced_queryset.prefetch_related("scripts", "custom_code")

    def export_serialized(
        self,
        builder,
        import_export_config,
        files_zip=None,
        storage=None,
        progress_builder=None,
    ) -> BuilderCustomCodeDict:
        """
        Serializes the scripts and the custom_code properties.
        """

        builder_dict = super().export_serialized(
            builder,
            import_export_config,
            files_zip=files_zip,
            storage=storage,
            progress_builder=progress_builder,
        )

        scripts = [
            {
                "type": s.type,
                "url": s.url,
                "load_type": s.load_type,
                "crossorigin": s.crossorigin,
            }
            for s in builder.scripts.all()
        ]

        return BuilderCustomCodeDict(
            **builder_dict,
            scripts=scripts,
            custom_code={"css": builder.custom_code.css, "js": builder.custom_code.js},
        )

    def import_serialized(
        self,
        workspace,
        serialized_values,
        import_export_config,
        id_mapping,
        files_zip=None,
        storage=None,
        progress_builder=None,
    ) -> Builder:
        """
        Handles the scripts and the custom_code properties.
        """

        serialized_scripts = serialized_values.pop("scripts", [])
        serialized_custom_code = serialized_values.pop(
            "custom_code", {"css": "", "js": ""}
        )

        instance = super().import_serialized(
            workspace,
            serialized_values,
            import_export_config,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            progress_builder=progress_builder,
        )

        instance.custom_code.css = serialized_custom_code["css"]
        instance.custom_code.js = serialized_custom_code["js"]
        instance.custom_code.save()

        self._create_scripts_in_bulk(instance, serialized_scripts)

        return instance
