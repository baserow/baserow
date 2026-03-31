export class BaserowFormulaParserError extends Error {
  constructor(offendingSymbol, line, character, message) {
    super()
    this.offendingSymbol = offendingSymbol
    this.line = line
    this.character = character
    this.message = message
  }
}

export class UnknownOperatorError extends Error {
  constructor(operatorName) {
    super()
    this.operatorName = operatorName
  }
}

/**
 * A base class for errors that are meant to be shown to the user. These errors
 * should have a human-readable message that can be directly shown to the user,
 * and should not contain any technical info about the formula parser or runtime
 */
export class BaseHumanReadableError extends Error {
  isHumanReadableError = true
}

export class InvalidNumberOfArguments extends BaseHumanReadableError {
  constructor(formulaFunctionType, minArgs, maxArgs = null) {
    super()
    this.formulaFunctionType = formulaFunctionType
    this.minArgs = minArgs
    this.maxArgs = maxArgs
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

export class InvalidFormulaType extends BaseHumanReadableError {
  constructor(message) {
    super()
    this.message = message
  }
}

export class InvalidFormulaArgumentType extends BaseHumanReadableError {
  constructor(formulaFunctionType, arg) {
    super()
    this.formulaFunctionType = formulaFunctionType
    this.arg = arg
  }
}

export class InvalidFormulaArgument extends BaseHumanReadableError {
  constructor(arg, message) {
    super()
    this.arg = arg
    this.message = message
  }
}

