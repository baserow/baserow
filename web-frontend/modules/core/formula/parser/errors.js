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
  constructor(args, message) {
    super()
    this.args = args
    this.message = message
    this.scope = 'argument'
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
