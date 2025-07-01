from baserow_premium.builder.application_types import PremiumBuilderApplicationType

from baserow_enterprise.builder.custom_code.application_type_mixin import (
    CustomCodeBuilderApplicationTypeMixin,
)


class EnterpriseBuilderApplicationType(
    CustomCodeBuilderApplicationTypeMixin,
    PremiumBuilderApplicationType,
):
    ...
