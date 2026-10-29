from copy import deepcopy

from baserow.core.formula.field import JSONFormulaField


class TargetFiltersField(JSONFormulaField):
    """Store formulas in both contributed condition groups in compact form."""

    def transform_values(self, value, transform):
        value = deepcopy(value)
        for link in value or []:
            for key in ("group", "alternative_group"):
                for condition in (link.get(key) or {}).get("filters", []):
                    condition["value"] = transform(condition.get("value", ""))
        return value

    def _transform_db_properties(self, value):
        return self.transform_values(value, self._transform_db_property)

    def get_prep_value(self, value):
        return self.transform_values(value, self._transform_python_property)
