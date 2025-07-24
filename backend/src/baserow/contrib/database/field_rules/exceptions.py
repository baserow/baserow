class FieldRuleError(Exception):
    pass


class FieldRuleTableMismatch(FieldRuleError):
    pass


class NoRuleError(FieldRuleError):
    pass
