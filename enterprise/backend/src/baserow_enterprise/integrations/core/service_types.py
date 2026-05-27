from baserow.contrib.integrations.core.service_types import CoreServiceType
from baserow.core.services.registries import DispatchTypes
from baserow.core.services.types import ServiceDict
from baserow_enterprise.integrations.core.models import CoreCodeService


class CoreCodeServiceType(CoreServiceType):
    type = "code"
    model_class = CoreCodeService
    dispatch_types = [DispatchTypes.ACTION]
    allowed_fields = ["code"]
    serializer_field_names = ["code"]
    simple_formula_fields = ["code"]

    class SerializedDict(ServiceDict):
        code: str

    @property
    def serializer_field_overrides(self):
        from baserow.core.formula.serializers import FormulaSerializerField

        return {
            "code": FormulaSerializerField(
                help_text=CoreCodeService._meta.get_field("code").help_text,
                required=False,
            ),
        }
