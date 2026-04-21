from django.apps import AppConfig


class AssetManagementConfig(AppConfig):
    name = "baserow.core.asset_management"
    verbose_name = "Asset Management"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import baserow.core.asset_management.signals  # noqa: F401
