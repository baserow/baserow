import { Registerable } from '@baserow/modules/core/registry'
import {
  NumberBaserowRuntimeFormulaArgumentType,
  TextBaserowRuntimeFormulaArgumentType,
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
}
