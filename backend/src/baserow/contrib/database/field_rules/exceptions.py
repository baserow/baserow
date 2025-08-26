class FieldRuleError(Exception):
    pass


class FieldRuleTableMismatch(FieldRuleError):
    pass


class NoRuleError(FieldRuleError):
    pass


class FieldRuleAlreadyExistsError(FieldRuleError):
    pass
