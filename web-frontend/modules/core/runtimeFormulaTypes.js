import { Registerable } from '@baserow/modules/core/registry'
import {
  NumberBaserowRuntimeFormulaArgumentType,
  TextBaserowRuntimeFormulaArgumentType,
  DateTimeBaserowRuntimeFormulaArgumentType,
  ObjectBaserowRuntimeFormulaArgumentType,
  BooleanBaserowRuntimeFormulaArgumentType,
  TimezoneBaserowRuntimeFormulaArgumentType,
  AnyBaserowRuntimeFormulaArgumentType,
  ArrayBaserowRuntimeFormulaArgumentType,
} from '@baserow/modules/core/runtimeFormulaArgumentTypes'
import {
  InvalidFormulaArgumentType,
  InvalidNumberOfArguments,
} from '@baserow/modules/core/formula/parser/errors'
import { Node, VueNodeViewRenderer } from '@tiptap/vue-2'
import { reverseString } from '@baserow/modules/core/utils/string'
import { avg, sum } from '@baserow/modules/core/utils/number'
import {
  ensureString,
  ensureArray,
} from '@baserow/modules/core/utils/validator'
import GetFormulaComponent from '@baserow/modules/core/components/formula/GetFormulaComponent'
import { mergeAttributes } from '@tiptap/core'
import { FORMULA_CATEGORY, FORMULA_TYPE } from '@baserow/modules/core/enums'
import _ from 'lodash'
import moment from '@baserow/modules/core/moment'

export class RuntimeFormulaFunction extends Registerable {
  /**
   * Must return an object containing the category name and icon class of the formula.
   */
  static getCategoryType() {
    throw new Error('The category type of a formula function must be set.')
  }

  /**
   * Must return a string indicating the valid formula type.
   */
  static getFormulaType() {
    throw new Error('The formula type of a formula function must be set.')
  }

  /**
   * Should define the arguments the function has. If null then we don't know what
   * arguments the function has any anything is accepted.
   *
   * @returns {Array<BaserowRuntimeFormulaArgumentType> || null}
   */
  get args() {
    return null
  }

  /**
   * The number of arguments the execute function expects
   * @returns {null|number}
   */
  get numArgs() {
    return this.args === null ? null : this.args.length
  }

  /**
   * This is the main function that will produce a result for the defined formula
   *
   * @param {Object} context - The data the function has access to
   * @param {Array} args - The arguments that the function should be executed with
   * @returns {any} - The result of executing the function
   */
  execute(context, args) {
    return null
  }

  /**
   * This function can be called to validate all arguments given to the formula
   *
   * @param args - The arguments provided to the formula
   * @throws InvalidNumberOfArguments - If the number of arguments is incorrect
   * @throws InvalidFormulaArgumentType - If any of the arguments have a wrong type
   */
  validateArgs(args, validateType = true) {
    if (!this.validateNumberOfArgs(args)) {
      throw new InvalidNumberOfArguments(this, args)
    }
    if (validateType) {
      const invalidArg = this.validateTypeOfArgs(args)
      if (invalidArg) {
        throw new InvalidFormulaArgumentType(this, invalidArg)
      }
    }
  }

  /**
   * This function validates that the number of args is correct.
   *
   * @param args - The args passed to the execute function
   * @returns {boolean} - If the number is correct.
   */
  validateNumberOfArgs(args) {
    if (this.numArgs === null) return true

    const requiredArgs = this.args.filter((arg) => !arg.optional).length
    const totalArgs = this.args.length

    return args.length >= requiredArgs && args.length <= totalArgs
  }

  /**
   * This function validates that the type of all args is correct.
   * If a type is incorrect it will return that arg.
   *
   * @param args - The args that are being checked
   * @returns {any} - The arg that has the wrong type, if any
   */
  validateTypeOfArgs(args) {
    if (this.args === null) {
      return null
    }

    return args.find((arg, index) => !this.args[index].test(arg))
  }

  /**
   * This function parses the arguments before they get handed over to the execute
   * function. This allows us to cast any args that might be of the wrong type to
   * the correct type or transform the data in any other way we wish to.
   *
   * @param args - The args that are being parsed
   * @returns {*} - The args after they were parsed
   */
  parseArgs(args) {
    if (this.args === null) {
      return args
    }

    return args.map((arg, index) => this.args[index].parse(arg))
  }

  /**
   * The type name of the formula component that should be used to render the formula
   * in the editor.
   * @returns {string || null}
   */
  get formulaComponentType() {
    return null
  }

  /**
   * The component configuration that should be used to render the formula in the
   * editor.
   *
   * @returns {null}
   */
  get formulaComponent() {
    return null
  }

  /**
   * This function returns one or many nodes that can be used to render the formula
   * in the editor.
   *
   * @param args - The args that are being parsed
   * @param mode - The mode of the formula editor ('simple', 'advanced', or 'raw')
   * @returns {object || Array} - The component configuration or a list of components
   */
  toNode(args, mode = 'simple') {
    return {
      type: this.formulaComponentType,
    }
  }

  getDescription() {
    throw new Error(
      'Not implemented error. This method should return the functions description.'
    )
  }

  getExamples() {
    throw new Error(
      'Not implemented error. This method should return list of strings showing ' +
        'example usage of the function.'
    )
  }

  getCategory() {
    const { i18n } = this.app
    return i18n.t(`runtimeFormulaTypes.${this.getCategoryType().category}`)
  }

  getIconClass() {
    return this.getCategoryType().iconClass
  }

  /**
   * If the formula type is 'operator', returns the correct literal
   * operator symbol. Otherwise returns null.
   * @returns {string|null}
   */
  get getOperatorSymbol() {
    return null
  }
}

export class RuntimeConcat extends RuntimeFormulaFunction {
  static getType() {
    return 'concat'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  execute(context, args) {
    return args.map((arg) => ensureString(arg)).join('')
  }

  validateNumberOfArgs(args) {
    return args.length > 1
  }

  toNode(args, mode = 'simple') {
    // In advanced mode, we want to show the formula as-is with quotes
    if (mode === 'advanced') {
      return {
        type: this.formulaComponentType,
      }
    }

    // In simple mode, recognize root concat that adds the new lines between paragraphs
    if (args.every((arg, index) => index % 2 === 0 || arg.type === 'newLine')) {
      return args
        .filter((arg, index) => index % 2 === 0) // Remove the new lines elements
        .map((arg) => {
          // If arg is already a wrapper, extract its content; otherwise wrap it
          const content =
            arg?.type === 'wrapper' && arg.content ? arg.content : [arg].flat()
          return { type: 'wrapper', content }
        })
    }
    return { type: 'wrapper', content: args }
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.concatDescription')
  }

  getExamples() {
    return [
      { formula: "concat('Hello,', ' World!')", result: '"Hello, world!"' },
      {
        formula: "concat(get('data_source.1.0.field_1'), ' bar')",
        result: '"foo bar"',
      },
    ]
  }
}

export class RuntimeGet extends RuntimeFormulaFunction {
  static getType() {
    return 'get'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [new TextBaserowRuntimeFormulaArgumentType()]
  }

  get formulaComponentType() {
    return 'get-formula-component'
  }

  get formulaComponent() {
    const formulaComponentType = this.formulaComponentType
    return Node.create({
      name: formulaComponentType,
      group: 'inline',
      inline: true,
      selectable: false,
      atom: true,
      addNodeView() {
        return VueNodeViewRenderer(GetFormulaComponent)
      },
      addAttributes() {
        return {
          path: {
            default: '',
          },
          isSelected: {
            default: false,
          },
        }
      },
      parseHTML() {
        return [
          {
            tag: formulaComponentType,
          },
        ]
      },
      renderHTML({ HTMLAttributes }) {
        return [formulaComponentType, mergeAttributes(HTMLAttributes)]
      },
    })
  }

  execute(context, args) {
    return context[args[0]]
  }

  toNode(args) {
    const [textNode] = args
    const defaultConfiguration = super.toNode(args)
    const specificConfiguration = {
      attrs: {
        path: textNode.text,
        isSelected: false,
      },
    }
    return _.merge(specificConfiguration, defaultConfiguration)
  }

  fromNodeToFormula(node) {
    return `get('${node.attrs.path}')`
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.getDescription')
  }

  getExamples() {
    return [
      {
        formula: "get('previous_node.1.body')",
        result: "'Hello world'",
      },
    ]
  }
}

export class RuntimeAdd extends RuntimeFormulaFunction {
  static getType() {
    return 'add'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get getOperatorSymbol() {
    return '+'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0] + args[1]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.addDescription')
  }

  getExamples() {
    return [
      {
        formula: '2 + 3',
        result: '5',
      },
      {
        formula: '1 + 2 + 3',
        result: '6',
      },
    ]
  }
}

export class RuntimeMinus extends RuntimeFormulaFunction {
  static getType() {
    return 'minus'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get getOperatorSymbol() {
    return '-'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0] - args[1]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.minusDescription')
  }

  getExamples() {
    return [
      {
        formula: '3 - 2',
        result: '1',
      },
      {
        formula: '5 - 2 - 1',
        result: '2',
      },
    ]
  }
}

export class RuntimeMultiply extends RuntimeFormulaFunction {
  static getType() {
    return 'multiply'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get getOperatorSymbol() {
    return '*'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0] * args[1]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.multiplyDescription')
  }

  getExamples() {
    return [
      {
        formula: '2 * 3',
        result: '6',
      },
      {
        formula: '2 * 3 * 3',
        result: '18',
      },
    ]
  }
}

export class RuntimeDivide extends RuntimeFormulaFunction {
  static getType() {
    return 'divide'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get getOperatorSymbol() {
    return '/'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0] / args[1]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.divideDescription')
  }

  getExamples() {
    return [
      {
        formula: '6 / 2',
        result: '3',
      },
      {
        formula: '15 / 2 / 2',
        result: '3.75',
      },
    ]
  }
}

export class RuntimeEqual extends RuntimeFormulaFunction {
  static getType() {
    return 'equal'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get getOperatorSymbol() {
    return '='
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a === b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.equalDescription')
  }

  getExamples() {
    return [
      {
        formula: '2 = 3',
        result: 'false',
      },
      {
        formula: '"foo" = "bar"',
        result: 'false',
      },
      {
        formula: '"foo" = "foo"',
        result: 'true',
      },
      {
        formula: 'now() = now()',
        result: 'false',
      },
    ]
  }
}

export class RuntimeNotEqual extends RuntimeFormulaFunction {
  static getType() {
    return 'not_equal'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get getOperatorSymbol() {
    return '!='
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a !== b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.notEqualDescription')
  }

  getExamples() {
    return [
      {
        formula: '2 != 3',
        result: 'true',
      },
      {
        formula: '"foo" != "foo"',
        result: 'false',
      },
      {
        formula: '"foo" != "bar"',
        result: 'true',
      },
      {
        formula: 'now() != now()',
        result: 'true',
      },
    ]
  }
}

export class RuntimeGreaterThan extends RuntimeFormulaFunction {
  static getType() {
    return 'greater_than'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get getOperatorSymbol() {
    return '>'
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    const typeA = typeof a
    const typeB = typeof b

    if (typeA === 'number' && typeB === 'number') {
      return a > b
    }

    if (typeA === 'string' && typeB === 'string') {
      return a > b
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.greaterThanDescription')
  }

  getExamples() {
    return [
      {
        formula: '5 > 4',
        result: 'true',
      },
      {
        formula: '"a" > "b"',
        result: 'false',
      },
      {
        formula: '"Ambarella" > "fig"',
        result: 'false',
      },
      {
        formula: 'now() > now()',
        result: 'false',
      },
    ]
  }
}

export class RuntimeLessThan extends RuntimeFormulaFunction {
  static getType() {
    return 'less_than'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get getOperatorSymbol() {
    return '<'
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    const typeA = typeof a
    const typeB = typeof b

    if (typeA === 'number' && typeB === 'number') {
      return a < b
    }

    if (typeA === 'string' && typeB === 'string') {
      return a < b
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.lessThanDescription')
  }

  getExamples() {
    return [
      {
        formula: '2 < 3',
        result: 'true',
      },
      {
        formula: '"b" < "a"',
        result: 'false',
      },
      {
        formula: '"Ambarella" < "fig"',
        result: 'true',
      },
      {
        formula: 'now() < now()',
        result: 'true',
      },
    ]
  }
}

export class RuntimeGreaterThanOrEqual extends RuntimeFormulaFunction {
  static getType() {
    return 'greater_than_or_equal'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get getOperatorSymbol() {
    return '>='
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    const typeA = typeof a
    const typeB = typeof b

    if (typeA === 'number' && typeB === 'number') {
      return a >= b
    }

    if (typeA === 'string' && typeB === 'string') {
      return a >= b
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.greaterThanOrEqualDescription')
  }

  getExamples() {
    return [
      {
        formula: '3 >= 2',
        result: 'false',
      },
      {
        formula: '"b" >= "a"',
        result: 'true',
      },
      {
        formula: '"Ambarella" >= "fig"',
        result: 'false',
      },
      {
        formula: 'now() >= now()',
        result: 'false',
      },
    ]
  }
}

export class RuntimeLessThanOrEqual extends RuntimeFormulaFunction {
  static getType() {
    return 'less_than_or_equal'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get getOperatorSymbol() {
    return '<='
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    const typeA = typeof a
    const typeB = typeof b

    if (typeA === 'number' && typeB === 'number') {
      return a <= b
    }

    if (typeA === 'string' && typeB === 'string') {
      return a <= b
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.lessThanDescription')
  }

  getExamples() {
    return [
      {
        formula: '3 <= 3',
        result: 'true',
      },
      {
        formula: '"a" <= "b"',
        result: 'false',
      },
      {
        formula: '"fig" <= "Ambarella"',
        result: 'false',
      },
      {
        formula: 'now() <= now()',
        result: 'true',
      },
    ]
  }
}

export class RuntimeUpper extends RuntimeFormulaFunction {
  static getType() {
    return 'upper'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [new TextBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [s]) {
    return s.toUpperCase()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.upperDescription')
  }

  getExamples() {
    return [
      {
        formula: "upper('Hello, World!')",
        result: "'HELLO, WORLD!'",
      },
    ]
  }
}

export class RuntimeLower extends RuntimeFormulaFunction {
  static getType() {
    return 'lower'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [new TextBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [s]) {
    return s.toLowerCase()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.lowerDescription')
  }

  getExamples() {
    return [
      {
        formula: "lower('Hello, World!')",
        result: "'hello, world!'",
      },
    ]
  }
}

export class RuntimeCapitalize extends RuntimeFormulaFunction {
  static getType() {
    return 'capitalize'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [new TextBaserowRuntimeFormulaArgumentType()]
  }

  capitalize(str) {
    if (!str) return ''
    const [firstChar, ...remainingChars] = [...str]
    return firstChar.toUpperCase() + remainingChars.join('').toLowerCase()
  }

  execute(context, [s]) {
    return this.capitalize(s)
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.capitalizeDescription')
  }

  getExamples() {
    return [
      {
        formula: "capitalize('hello, world!')",
        result: "'Hello, world!'",
      },
    ]
  }
}

export class RuntimeRound extends RuntimeFormulaFunction {
  static getType() {
    return 'round'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType({
        optional: true,
        castToInt: true,
      }),
    ]
  }

  execute(context, args) {
    // Default to 2 decimal places
    let decimalPlaces = 2

    if (args.length === 2) {
      // Avoid negative numbers
      decimalPlaces = Math.max(args[1], 0)
    }

    return Number(args[0].toFixed(decimalPlaces))
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.roundDescription')
  }

  getExamples() {
    return [
      {
        formula: "round('12.345', 2)",
        result: '12.35',
      },
    ]
  }
}

export class RuntimeIsEven extends RuntimeFormulaFunction {
  static getType() {
    return 'is_even'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get args() {
    return [new NumberBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [n]) {
    return n % 2 === 0
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.evenDescription')
  }

  getExamples() {
    return [
      {
        formula: 'is_even(12)',
        result: 'true',
      },
      {
        formula: 'is_even(13)',
        result: 'false',
      },
    ]
  }
}

export class RuntimeIsOdd extends RuntimeFormulaFunction {
  static getType() {
    return 'is_odd'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get args() {
    return [new NumberBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [n]) {
    return n % 2 !== 0
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.oddDescription')
  }

  getExamples() {
    return [
      {
        formula: 'is_odd(11)',
        result: 'true',
      },
      {
        formula: 'is_odd(12)',
        result: 'false',
      },
    ]
  }
}

export class RuntimeDateTimeFormat extends RuntimeFormulaFunction {
  static getType() {
    return 'datetime_format'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return [
      new DateTimeBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType(),
      new TimezoneBaserowRuntimeFormulaArgumentType({ optional: true }),
    ]
  }

  execute(context, args) {
    const [
      datetime,
      momentFormat,
      timezone = Intl.DateTimeFormat().resolvedOptions().timeZone,
    ] = args

    return moment(datetime).tz(timezone).format(momentFormat)
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.dateTimeDescription')
  }

  getExamples() {
    return [
      {
        formula: "datetime_format(now(), 'YYYY-MM-DD')",
        result: "'2025-11-03'",
      },
      {
        formula: "datetime_format(now(), 'YYYY-MM-DD', 'Europe/Amsterdam')",
        result: "'2025-11-03'",
      },
      {
        formula: "datetime_format(now(), 'DD/MM/YYYY HH:mm:ss', 'UTC')",
        result: "'03/11/2025 12:12:09'",
      },
    ]
  }
}

export class RuntimeDay extends RuntimeFormulaFunction {
  static getType() {
    return 'day'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return [new DateTimeBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [datetime]) {
    return datetime.getDate()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.dayDescription')
  }

  getExamples() {
    return [
      {
        formula: "day('2025-10-16 11:05:38')",
        result: '16',
      },
    ]
  }
}

export class RuntimeMonth extends RuntimeFormulaFunction {
  static getType() {
    return 'month'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return [new DateTimeBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [datetime]) {
    return datetime.getMonth()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.monthDescription')
  }

  getExamples() {
    // Month is 0 indexed
    return [
      {
        formula: "month('2025-10-16 11:05:38')",
        result: '9',
      },
    ]
  }
}

export class RuntimeYear extends RuntimeFormulaFunction {
  static getType() {
    return 'year'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return [new DateTimeBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [datetime]) {
    return datetime.getFullYear()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.yearDescription')
  }

  getExamples() {
    return [
      {
        formula: "year('2025-10-16 11:05:38')",
        result: '2025',
      },
    ]
  }
}

export class RuntimeHour extends RuntimeFormulaFunction {
  static getType() {
    return 'hour'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return [new DateTimeBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [datetime]) {
    return datetime.getHours()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.hourDescription')
  }

  getExamples() {
    return [
      {
        formula: "hour('2025-10-16 11:05:38')",
        result: '11',
      },
    ]
  }
}

export class RuntimeMinute extends RuntimeFormulaFunction {
  static getType() {
    return 'minute'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return [new DateTimeBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [datetime]) {
    return datetime.getMinutes()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.minuteDescription')
  }

  getExamples() {
    return [
      {
        formula: "minute('2025-10-16T11:05:38')",
        result: '5',
      },
    ]
  }
}

export class RuntimeSecond extends RuntimeFormulaFunction {
  static getType() {
    return 'second'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return [new DateTimeBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [datetime]) {
    return datetime.getSeconds()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.secondDescription')
  }

  getExamples() {
    return [
      {
        formula: "second('2025-10-16 11:05:38')",
        result: '38',
      },
    ]
  }
}

export class RuntimeNow extends RuntimeFormulaFunction {
  static getType() {
    return 'now'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return []
  }

  execute(context, args) {
    return new Date()
  }

  getExamples() {
    return [
      {
        formula: 'now()',
        result: "'2025-10-16 11:05:38'",
      },
    ]
  }
}

export class RuntimeToday extends RuntimeFormulaFunction {
  static getType() {
    return 'today'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.DATE
  }

  get args() {
    return []
  }

  execute(context, args) {
    return new Date().toISOString().split('T')[0]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.todayDescription')
  }

  getExamples() {
    return [
      {
        formula: 'today()',
        result: "'2025-10-16'",
      },
    ]
  }
}

export class RuntimeGetProperty extends RuntimeFormulaFunction {
  static getType() {
    return 'get_property'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [
      new ObjectBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0][args[1]]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.getPropertyDescription')
  }

  getExamples() {
    return [
      {
        formula: 'get_property(\'{"cherry": "red"}\', \'cherry\')',
        result: "'red'",
      },
    ]
  }
}

export class RuntimeRandomInt extends RuntimeFormulaFunction {
  static getType() {
    return 'random_int'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType({ castToInt: true }),
      new NumberBaserowRuntimeFormulaArgumentType({ castToInt: true }),
    ]
  }

  execute(context, args) {
    const min = Math.ceil(args[0])
    const max = Math.floor(args[1])
    return Math.floor(Math.random() * (max - min + 1) + min)
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.randomIntDescription')
  }

  getExamples() {
    return [
      {
        formula: 'random_int(10, 20)',
        result: '17',
      },
    ]
  }
}

export class RuntimeRandomFloat extends RuntimeFormulaFunction {
  static getType() {
    return 'random_float'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType({ castToFloat: true }),
      new NumberBaserowRuntimeFormulaArgumentType({ castToFloat: true }),
    ]
  }

  execute(context, args) {
    return Math.random() * (args[1] - args[0]) + args[0]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.randomFloatDescription')
  }

  getExamples() {
    return [
      {
        formula: 'random_float(10, 20)',
        result: '18.410550297490616',
      },
    ]
  }
}

export class RuntimeRandomBool extends RuntimeFormulaFunction {
  static getType() {
    return 'random_bool'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get args() {
    return []
  }

  execute(context, args) {
    return Math.random() < 0.5
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.randomBoolDescription')
  }

  getExamples() {
    return [
      {
        formula: 'random_bool()',
        result: 'true',
      },
    ]
  }
}

export class RuntimeGenerateUUID extends RuntimeFormulaFunction {
  static getType() {
    return 'generate_uuid'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return []
  }

  execute(context, args) {
    return crypto.randomUUID()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.generateUUIDDescription')
  }

  getExamples() {
    return [
      {
        formula: 'generate_uuid()',
        result: "'9b772ad6-08bc-4d19-958d-7f1c21a4f4ef'",
      },
    ]
  }
}

export class RuntimeIf extends RuntimeFormulaFunction {
  static getType() {
    return 'if'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.CONDITION
  }

  get args() {
    return [
      new BooleanBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0] ? args[1] : args[2]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.ifDescription')
  }

  getExamples() {
    return [
      {
        formula: 'if(true, true, false)',
        result: 'true',
      },
      {
        formula:
          "if(random_bool(), 'Random bool is true', 'Random bool is false')",
        result: "'Random bool is false'",
      },
    ]
  }
}

export class RuntimeAnd extends RuntimeFormulaFunction {
  static getType() {
    return 'and'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.CONDITION
  }

  get getOperatorSymbol() {
    return '&&'
  }

  get args() {
    return [
      new BooleanBaserowRuntimeFormulaArgumentType(),
      new BooleanBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0] && args[1]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.andDescription')
  }

  getExamples() {
    return [
      {
        formula: 'true && true',
        result: 'true',
      },
      {
        formula: 'true && true && false',
        result: 'false',
      },
    ]
  }
}

export class RuntimeOr extends RuntimeFormulaFunction {
  static getType() {
    return 'or'
  }

  static getFormulaType() {
    return FORMULA_TYPE.OPERATOR
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.CONDITION
  }

  get getOperatorSymbol() {
    return '||'
  }

  get args() {
    return [
      new BooleanBaserowRuntimeFormulaArgumentType(),
      new BooleanBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0] || args[1]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.orDescription')
  }

  getExamples() {
    return [
      {
        formula: 'true || true',
        result: 'true',
      },
      {
        formula: 'true || true || false',
        result: 'true',
      },
      {
        formula: 'false || false',
        result: 'false',
      },
    ]
  }
}

export class RuntimeReplace extends RuntimeFormulaFunction {
  static getType() {
    return 'replace'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [
      new TextBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return args[0].replaceAll(args[1], args[2])
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.replaceDescription')
  }

  getExamples() {
    return [
      {
        formula: "replace('Hello, world!', 'l', '-')",
        result: "'He--o, wor-d!'",
      },
    ]
  }
}

export class RuntimeLength extends RuntimeFormulaFunction {
  static getType() {
    return 'length'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [new AnyBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [value]) {
    if (Array.isArray(value)) {
      return value.length
    } else if (value !== null && typeof value === 'object') {
      return Object.keys(value).length
    } else if (typeof value === 'string') {
      return value.length
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.lengthDescription')
  }

  getExamples() {
    return [
      {
        formula: "length('Hello, world!')",
        result: '13',
      },
      {
        formula: 'length(to_array("foo, bar"))',
        result: '2',
      },
    ]
  }
}

export class RuntimeContains extends RuntimeFormulaFunction {
  static getType() {
    return 'contains'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new AnyBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    const value = args[0]
    const toCheck = args[1]

    if (Array.isArray(value)) {
      return value.includes(toCheck)
    } else if (value !== null && typeof value === 'object') {
      return Object.keys(value).includes(toCheck)
    } else if (typeof value === 'string') {
      return value.includes(toCheck)
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.containsDescription')
  }

  getExamples() {
    return [
      {
        formula: "contains('Hello, world!', 'll')",
        result: 'true',
      },
      {
        formula: 'contains(to_array("foo, bar"), "foo")',
        result: 'true',
      },
    ]
  }
}

export class RuntimeReverse extends RuntimeFormulaFunction {
  static getType() {
    return 'reverse'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [new AnyBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [arg]) {
    if (Array.isArray(arg)) {
      return arg.reverse()
    }

    if (typeof arg === 'string') {
      return reverseString(arg)
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.reverseDescription')
  }

  getExamples() {
    return [
      {
        formula: "reverse('Hello, world!')",
        result: "'!dlrow ,olleH'",
      },
      {
        formula: "reverse('😀💙🚀')",
        result: "'🚀💙😀",
      },
      {
        formula: 'reverse(to_array("foo, bar"))',
        result: "'bar,foo'",
      },
    ]
  }
}

export class RuntimeJoin extends RuntimeFormulaFunction {
  static getType() {
    return 'join'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType({ optional: true }),
    ]
  }

  execute(context, args) {
    const val = args[0]
    let separator = ','
    if (args.length === 2) {
      separator = args[1]
    }

    if (Array.isArray(val)) {
      return val.join(separator)
    }

    if (typeof val === 'string') {
      return val.split('').join(separator)
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.joinDescription')
  }

  getExamples() {
    return [
      {
        formula: 'join(to_array("foo, bar"))',
        result: "'foo,bar'",
      },
      {
        formula: 'join(to_array("foo, bar"), " * ")',
        result: "'foo * bar'",
      },
    ]
  }
}

export class RuntimeSplit extends RuntimeFormulaFunction {
  static getType() {
    return 'split'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [
      new TextBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType({ optional: true }),
    ]
  }

  execute(context, args) {
    let separator = ''
    if (args.length === 2) {
      separator = args[1]
    }
    return args[0].split(separator)
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.splitDescription')
  }

  getExamples() {
    return [
      {
        formula: 'split("foobar")',
        result: "'f,o,o,b,a,r'",
      },
      {
        formula: 'split("foobar", "b")',
        result: "'foo,ar'",
      },
    ]
  }
}

export class RuntimeIsEmpty extends RuntimeFormulaFunction {
  static getType() {
    return 'is_empty'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.BOOLEAN
  }

  get args() {
    return [new AnyBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [arg]) {
    if (arg === undefined || arg === null) {
      return true
    }

    if (Array.isArray(arg)) {
      return arg.length === 0
    }

    if (typeof arg === 'object') {
      return Object.keys(arg).length === 0
    }

    if (typeof arg === 'string') {
      return arg.trim().length === 0
    }

    return false
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.isEmptyDescription')
  }

  getExamples() {
    return [
      {
        formula: "is_empty('')",
        result: 'true',
      },
      {
        formula: 'is_empty(0)',
        result: 'true',
      },
      {
        formula: 'is_empty(to_array(""))',
        result: 'true',
      },
      {
        formula: "is_empty('foo')",
        result: 'false',
      },
      {
        formula: 'is_empty(1)',
        result: 'false',
      },
      {
        formula: 'is_empty(to_array("foo,bar"))',
        result: 'false',
      },
    ]
  }
}

export class RuntimeStrip extends RuntimeFormulaFunction {
  static getType() {
    return 'strip'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [new TextBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [arg]) {
    if (typeof arg === 'string' && isNaN(Number(arg))) {
      return arg.trim()
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.stripDescription')
  }

  getExamples() {
    return [
      {
        formula: "strip(' foo ')",
        result: "'foo'",
      },
    ]
  }
}

export class RuntimeSum extends RuntimeFormulaFunction {
  static getType() {
    return 'sum'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get args() {
    return [new ArrayBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [arg]) {
    try {
      return sum(arg, { strict: true })
    } catch {
      return null
    }
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.sumDescription')
  }

  getExamples() {
    return [
      {
        formula: 'sum(to_array("1, 2, 3"))',
        result: '6',
      },
      {
        formula: 'sum(to_array("1, 2.5, 3"))',
        result: '6.5',
      },
    ]
  }
}

export class RuntimeAvg extends RuntimeFormulaFunction {
  static getType() {
    return 'avg'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.NUMBER
  }

  get args() {
    return [new ArrayBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [arg]) {
    try {
      return avg(arg, { strict: true })
    } catch {
      return null
    }
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.avgDescription')
  }

  getExamples() {
    return [
      {
        formula: "avg(to_array('1, 2, 3, 4'))",
        result: '2.5',
      },
    ]
  }
}

export class RuntimeAt extends RuntimeFormulaFunction {
  static getType() {
    return 'at'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [
      new AnyBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType({ castToInt: true }),
    ]
  }

  execute(context, args) {
    const [value, index] = args

    if (
      (Array.isArray(value) || typeof value === 'string') &&
      value.length > index
    ) {
      return value[index]
    }

    return null
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.atDescription')
  }

  getExamples() {
    return [
      {
        formula: 'at(to_array("foo, bar"), 1)',
        result: '"bar"',
      },
      {
        formula: 'at(to_array("foo, bar"), 3)',
        result: 'null',
      },
    ]
  }
}

export class RuntimeToArray extends RuntimeFormulaFunction {
  static getType() {
    return 'to_array'
  }

  static getFormulaType() {
    return FORMULA_TYPE.FUNCTION
  }

  static getCategoryType() {
    return FORMULA_CATEGORY.TEXT
  }

  get args() {
    return [new TextBaserowRuntimeFormulaArgumentType()]
  }

  execute(context, [arg]) {
    try {
      return ensureArray(arg)
    } catch {
      return null
    }
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.toArrayDescription')
  }

  getExamples() {
    return [
      {
        formula: "to_array('foo,bar')",
        result: '["foo", "bar"]',
      },
    ]
  }
}
