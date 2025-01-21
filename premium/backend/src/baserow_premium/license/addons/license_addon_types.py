from baserow_premium.license.addons.features import (
    APPLICATION_USER_SSO,
    CUSTOM_CSS_JS,
    PAYMENT_ELEMENT,
)
from baserow_premium.license.addons.registries import LicenseAddonType


class ProLicenseAddonType(LicenseAddonType):
    type = "pro"
    order = 10


class BusinessLicenseAddonType(LicenseAddonType):
    type = "business"
    order = 20
    features = [PAYMENT_ELEMENT, APPLICATION_USER_SSO, CUSTOM_CSS_JS]
