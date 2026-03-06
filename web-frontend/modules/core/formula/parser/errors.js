export class BaserowFormulaParserError extends Error {
  constructor(offendingSymbol, line, character, message) {
    super()
    this.offendingSymbol = offendingSymbol
    this.line = line
    this.character = character
    this.message = message
    this.scope = 'syntax'
  }
}

export class UnknownOperatorError extends Error {
  constructor(operatorName) {
    super()
    this.operatorName = operatorName
  }
}

export class InvalidNumberOfArguments extends Error {
  constructor(formulaFunctionType, minArgs, maxArgs = null) {
    super()
    this.formulaFunctionType = formulaFunctionType
    this.minArgs = minArgs
    this.maxArgs = maxArgs
    this.scope = 'argument'
    this.message = this.getMessage()
  }

  getMessage() {
    const ctx = {
      minArgs: this.minArgs,
      maxArgs: this.maxArgs,
      funcType: this.formulaFunctionType.getType()
    }
    const { app: { $i18n } } = this.formulaFunctionType
    // If we have a minimum, but no maximum, then this function needs >= minArgs arguments.
    if(this.minArgs && this.maxArgs === null) {
      return $i18n.t('formulaParserErrors.invalidArgCountMin', ctx)
    }
    // If the minimum and maximum are the same, then this function needs exactly minArgs (or maxArgs) arguments.
    else if(this.minArgs === this.maxArgs) {
      return $i18n.t('formulaParserErrors.invalidArgCountExact', ctx)
    }
    // Otherwise, this function wants a range between minArgs and maxArgs arguments.
    else {
      return $i18n.t('formulaParserErrors.invalidArgCountRange', ctx)
    }
  }
}

export class InvalidFormulaType extends Error {
  constructor(message) {
    super()
    this.scope = 'function'
    this.message = message
  }
}

export class InvalidFormulaArgumentType extends Error {
  constructor(formulaFunctionType, arg) {
    super()
    this.formulaFunctionType = formulaFunctionType
    this.scope = 'argument'
    this.arg = arg
  }
}

export class InvalidFormulaArgument extends Error {
  constructor(arg, message) {
    super()
    this.arg = arg
    this.scope = 'argument'
    this.message = message
  }
}

