import { Registerable } from '@baserow/modules/core/registry'
import {
  NumberBaserowRuntimeFormulaArgumentType,
  TextBaserowRuntimeFormulaArgumentType,
  DateTimeBaserowRuntimeFormulaArgumentType,
  ObjectBaserowRuntimeFormulaArgumentType,
} from '@baserow/modules/core/runtimeFormulaArgumentTypes'
import {
  InvalidFormulaArgumentType,
  InvalidNumberOfArguments,
} from '@baserow/modules/core/formula/parser/errors'
import { Node, VueNodeViewRenderer } from '@tiptap/vue-2'
import { ensureString } from '@baserow/modules/core/utils/validator'
import GetFormulaComponent from '@baserow/modules/core/components/formula/GetFormulaComponent'
import { mergeAttributes } from '@tiptap/core'
import _ from 'lodash'

export class RuntimeFormulaFunction extends Registerable {
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
  validateArgs(args) {
    if (!this.validateNumberOfArgs(args)) {
      throw new InvalidNumberOfArguments(this, args)
    }
    const invalidArg = this.validateTypeOfArgs(args)
    if (invalidArg) {
      throw new InvalidFormulaArgumentType(this, invalidArg)
    }
  }

  /**
   * This function validates that the number of args is correct.
   *
   * @param args - The args passed to the execute function
   * @returns {boolean} - If the number is correct.
   */
  validateNumberOfArgs(args) {
    return this.numArgs === null || args.length <= this.numArgs
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
   * @returns {object || Array} - The component configuration or a list of components
   */
  toNode(args) {
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
}

export class RuntimeConcat extends RuntimeFormulaFunction {
  static getType() {
    return 'concat'
  }

  execute(context, args) {
    return args.map((arg) => ensureString(arg)).join('')
  }

  validateNumberOfArgs(args) {
    return args.length >= 2
  }

  toNode(args) {
    // Recognize root concat that adds the new lines between paragraphs
    if (args.every((arg, index) => index % 2 === 0 || arg.type === 'newLine')) {
      return args
        .filter((arg, index) => index % 2 === 0) // Remove the new lines elements
        .map((arg) => ({ type: 'wrapper', content: [arg].flat() }))
    }
    return { type: 'wrapper', content: args }
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.concatDescription')
  }

  getExamples() {
    return ["concat('Hello,', ' World!') = 'Hello, world!'"]
  }
}

export class RuntimeGet extends RuntimeFormulaFunction {
  static getType() {
    return 'get'
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
    return ["get('previous_node.1.body')"]
  }
}

export class RuntimeAdd extends RuntimeFormulaFunction {
  static getType() {
    return 'add'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a + b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.addDescription')
  }

  getExamples() {
    return ['1+1+1 = 3', "'a' + 'b' = 'ab'"]
  }
}

export class RuntimeMinus extends RuntimeFormulaFunction {
  static getType() {
    return 'minus'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a - b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.minusDescription')
  }

  getExamples() {
    return ['3-1 = 2']
  }
}

export class RuntimeMultiply extends RuntimeFormulaFunction {
  static getType() {
    return 'multiply'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a * b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.multiplyDescription')
  }

  getExamples() {
    return ['2*3 = 6', "'a' * 3 = 'aaa'"]
  }
}

export class RuntimeDivide extends RuntimeFormulaFunction {
  static getType() {
    return 'divide'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a * b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.divideDescription')
  }

  getExamples() {
    return ['6/3 = 2']
  }
}

export class RuntimeEqual extends RuntimeFormulaFunction {
  static getType() {
    return 'equal'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
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
    return ['2=3 = false']
  }
}

export class RuntimeNotEqual extends RuntimeFormulaFunction {
  static getType() {
    return 'not_equal'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
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
    return ['2!=3 = true']
  }
}

export class RuntimeGreaterThan extends RuntimeFormulaFunction {
  static getType() {
    return 'greater_than'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a > b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.greaterThanDescription')
  }

  getExamples() {
    return ['3>2 = true']
  }
}

export class RuntimeLessThan extends RuntimeFormulaFunction {
  static getType() {
    return 'less_than'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a < b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.lessThanDescription')
  }

  getExamples() {
    return ['2<3 = true']
  }
}

export class RuntimeGreaterThanOrEqual extends RuntimeFormulaFunction {
  static getType() {
    return 'greater_than_or_equal'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a < b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.greaterThanOrEqualDescription')
  }

  getExamples() {
    return ['3>=3 = true']
  }
}

export class RuntimeLessThanOrEqual extends RuntimeFormulaFunction {
  static getType() {
    return 'less_than'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, [a, b]) {
    return a <= b
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.lessThanDescription')
  }

  getExamples() {
    return ['3<=3 = true']
  }
}

export class RuntimeUpper extends RuntimeFormulaFunction {
  static getType() {
    return 'upper'
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
    return ["upper('Hello, World!') = 'HELLO, WORLD!'"]
  }
}

export class RuntimeLower extends RuntimeFormulaFunction {
  static getType() {
    return 'lower'
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
    return ["lower('Hello, World!') = 'hello, world!'"]
  }
}

export class RuntimeCapitalize extends RuntimeFormulaFunction {
  static getType() {
    return 'capitalize'
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
    return ["capitalize('hello, world!') = 'Hello, world!'"]
  }
}

export class RuntimeRound extends RuntimeFormulaFunction {
  static getType() {
    return 'round'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    // Default to 2 decimal places?
    let decimalPlaces = 2

    if (args.length === 2) {
      // Avoid negative numbers
      decimalPlaces = Math.max(args[1], 0)
    }

    return args[0].toFixed(decimalPlaces)
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.roundDescription')
  }

  getExamples() {
    return ["round('12.345', 2) = '12.35'"]
  }
}

export class RuntimeIsEven extends RuntimeFormulaFunction {
  static getType() {
    return 'is_even'
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
    return ['even(12) = true']
  }
}

export class RuntimeIsOdd extends RuntimeFormulaFunction {
  static getType() {
    return 'is_odd'
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
    return ['odd(11) = true']
  }
}

export class RuntimeDateTimeFormat extends RuntimeFormulaFunction {
  static getType() {
    return 'datetime_format'
  }

  get args() {
    return [
      new DateTimeBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    // Backend uses Python's datetime formatting syntax, e.g. `%Y-%m-%d %H:%M:%S`
    // but I haven't yet found a way to replicate this in pure JS. Maybe
    // we can rely on a 3rd party lib?
    return 'TODO'
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.dateTimeDescription')
  }

  getExamples() {
    return [
      "datetime_format('2025-10-16 11:05:38.547989', '%Y-%m-%d', 'Asia/Dubai') = '2025-10-16'",
    ]
  }
}

export class RuntimeDay extends RuntimeFormulaFunction {
  static getType() {
    return 'day'
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
    return ["day('2025-10-16 11:05:38') = '16'"]
  }
}

export class RuntimeMonth extends RuntimeFormulaFunction {
  static getType() {
    return 'month'
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
    return ["month('2025-10-16 11:05:38') = '10'"]
  }
}

export class RuntimeYear extends RuntimeFormulaFunction {
  static getType() {
    return 'year'
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
    return ["year('2025-10-16 11:05:38') = '2025'"]
  }
}

export class RuntimeHour extends RuntimeFormulaFunction {
  static getType() {
    return 'hour'
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
    return ["hour('2025-10-16 11:05:38') = '11'"]
  }
}

export class RuntimeMinute extends RuntimeFormulaFunction {
  static getType() {
    return 'minute'
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
    return ["minute('2025-10-16 11:05:38') = '05'"]
  }
}

export class RuntimeSecond extends RuntimeFormulaFunction {
  static getType() {
    return 'second'
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
    return ["second('2025-10-16 11:05:38') = '38'"]
  }
}

export class RuntimeNow extends RuntimeFormulaFunction {
  static getType() {
    return 'now'
  }

  execute(context, args) {
    return new Date()
  }
}

export class RuntimeToday extends RuntimeFormulaFunction {
  static getType() {
    return 'today'
  }

  execute(context, args) {
    return new Date().toISOString().split('T')[0]
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.todayDescription')
  }

  getExamples() {
    return ["today() = '2025-10-16'"]
  }
}

export class RuntimeGetProperty extends RuntimeFormulaFunction {
  static getType() {
    return 'get_property'
  }

  get args() {
    return [
      new ObjectBaserowRuntimeFormulaArgumentType(),
      new TextBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    return new args[0][args[1]]()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.getPropertyDescription')
  }

  getExamples() {
    return ['get_property(\'{"cherry": "red"}\', "fruit")']
  }
}

export class RuntimeRandomInt extends RuntimeFormulaFunction {
  static getType() {
    return 'random_int'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
    ]
  }

  execute(context, args) {
    const min = Math.ceil(args[0])
    const max = Math.floor(args[1])
    return Math.floor(Math.random() * (max - min) + min)
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.randomIntDescription')
  }

  getExamples() {
    return ['random_int(10, 20) = 17']
  }
}

export class RuntimeRandomFloat extends RuntimeFormulaFunction {
  static getType() {
    return 'random_float'
  }

  get args() {
    return [
      new NumberBaserowRuntimeFormulaArgumentType(),
      new NumberBaserowRuntimeFormulaArgumentType(),
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
    return ['random_float(10, 20) = 18.410550297490616']
  }
}

export class RuntimeRandomBool extends RuntimeFormulaFunction {
  static getType() {
    return 'random_bool'
  }

  execute(context, args) {
    return Math.random() < 0.5
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.randomBoolDescription')
  }

  getExamples() {
    return ['random_bool() = true']
  }
}

export class RuntimeGenerateUUID extends RuntimeFormulaFunction {
  static getType() {
    return 'generate_uuid'
  }

  execute(context, args) {
    return crypto.randomUUID()
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('runtimeFormulaTypes.generateUUIDDescription')
  }

  getExamples() {
    return ["generate_uuid() = '9b772ad6-08bc-4d19-958d-7f1c21a4f4ef'"]
  }
}
