from baserow_premium.license.handler import LicenseHandler

from baserow.core.handler import CoreHandler
from baserow.core.registries import EmailContextType
from baserow_enterprise.features import ENTERPRISE_SETTINGS


class EnterpriseEmailContextType(EmailContextType):
    """
    An `EmailContextType` represents a context in which an email can be sent.
    """

    type = "enterprise"

    def get_context(self):
        from baserow.api.user_files.serializers import UserFileSerializer

        email_context = {}
        handler = CoreHandler()
        is_co_branding_feature_enabled = LicenseHandler.instance_has_feature(
            ENTERPRISE_SETTINGS
        )

        if (
            is_co_branding_feature_enabled
            and (custom_logo := handler.get_settings().co_branding_logo) is not None
        ):
            email_context["logo_url"] = UserFileSerializer(custom_logo).data["url"]
            email_context["logo_additional_text"] = "by Baserow"
            email_context["show_baserow_description"] = False

        return email_context
