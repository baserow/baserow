from baserow.contrib.builder.application_types import BuilderApplicationType
from baserow_enterprise.builder.custom_code.application_type_mixin import (
    CustomCodeBuilderApplicationTypeMixin,
)


class EnterpriseBuilderApplicationType(
    CustomCodeBuilderApplicationTypeMixin,
    BuilderApplicationType,
):
    ...
