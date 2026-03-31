import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'
import BaserowFormulaExecutionVisitor from '@baserow/modules/core/formula/parser/formulaExecutionVisitor.js'
import BaserowFormulaValidationVisitor from '@baserow/modules/core/formula/parser/formulaValidationVisitor.js'
import { FORMULA_TYPE } from '@baserow/modules/core/enums'

/**
 * Resolves a formula in the context of the given context.
 *
 * @param {object} formulaCtx the input formula.
 * @param {object} functions the functions that can be used in the formula.
 * @param {object} RuntimeFormulaContext the context given to the formula when we meet the
 *   `get('something')` expression
 * @returns the result of the formula in the given context.
 */
export const resolveFormula = (
  formulaCtx,
  functions,
  RuntimeFormulaContext
) => {
  if (!formulaCtx.formula) {
    return formulaCtx.formula
  }

  if (formulaCtx.mode === 'raw') {
    // We don't need to resolve the formula for raw mode.
    return formulaCtx.formula
  }

  try {
    const tree = parseBaserowFormula(formulaCtx.formula)
    return new BaserowFormulaExecutionVisitor(
      functions,
      RuntimeFormulaContext
    ).visit(tree)
  } catch (err) {
    console.debug(`FORMULA DEBUG: ${err}`)
    return null
  }
}

/**
 * Validates if a formula is syntactically correct and optionally validates
 * its arguments using the provided functions and validation context.
 *
 * @param {string} formula - The formula string to validate
 * @param {FunctionCollection} functions - The collection of available formula functions
 * @param {boolean} syntaxOnly - If true, only syntax is validated; if false, functions
 *  and their arguments are also validated.
 * @param validationContext - Context needed for validation (e.g., { dataProviderRegistry })
 * @param localisedInvalidSyntaxMessage - the localised 'Invalid formula syntax' message.
 *  Only used if the thrown error isn't human-readable (e.g. a syntax / runtime error).
 * @returns {Object} - Object with { scope: string, valid: boolean, errors: Array<string> }
 */
export const isFormulaValid = (
  formula,
  functions,
  syntaxOnly = true,
  validationContext = {},
  localisedInvalidSyntaxMessage = null
) => {
  if (!formula) {
    return { scope: null, valid: true, errors: [] }
  }
  try {
    const tree = parseBaserowFormula(formula)
    if (!syntaxOnly) {
      new BaserowFormulaValidationVisitor(functions, validationContext).visit(
        tree
      )
    }
    return { errors: [], valid: true, scope: null }
  } catch (err) {
    const isReadableError = err?.isHumanReadableError === true
    const fallbackMessage =
      localisedInvalidSyntaxMessage || 'Invalid formula syntax'
    return {
      valid: false,
      errors: [isReadableError ? err.message : fallbackMessage],
      scope: isReadableError ? 'human' : 'internal',
    }
  }
}

/**
 * Get all formula functions from the registry
 * @param {Object} app The app instance with registry
 * @returns {Object} All formula functions
 */
export const getFormulaFunctions = (app) => {
  return app.$registry.getAll('runtimeFormulaFunction')
}

/**
 * Get formula functions organized by category
 * @param {Object} app The app instance with registry
 * @param {Object} i18n The i18n instance (optional, will be extracted from app if not provided)
 * @returns {Array} Array of category nodes with their functions
 */
export const getFormulaFunctionsByCategory = (app, i18n = null) => {
  const functions = getFormulaFunctions(app)
  // Support both Option API (this.$t) and Composition API (app.i18n)
  const i18nInstance = i18n || app.i18n || app
  const categorizedFunctions = {}
  const categorizedOperators = {}

  // Group functions by category
  for (const [functionName, registryItem] of Object.entries(functions)) {
    try {
      // The registry might return instances instead of classes
      let instance = null
      let FunctionType = null

      // Check if registryItem is already an instance
      if (
        registryItem &&
        typeof registryItem === 'object' &&
        registryItem.constructor
      ) {
        // It's an instance, get its constructor
        FunctionType = registryItem.constructor
        instance = registryItem
      } else if (typeof registryItem === 'function') {
        // It's a constructor function
        FunctionType = registryItem
        instance = new FunctionType({ app })
      } else {
        // Skip items that are not valid constructors or instances
        continue
      }

      // Skip if getFormulaType is not defined (not a formula function)
      if (!FunctionType.getFormulaType) {
        continue
      }

      // Skip if getCategoryType is not defined
      if (!FunctionType.getCategoryType) {
        continue
      }

      // Get formula type
      const formulaType = FunctionType.getFormulaType()

      // Get category - use static method and format it
      const categoryType = FunctionType.getCategoryType()

      // Get translated category name
      let category = 'Other'
      const icon = categoryType.iconClass || 'iconoir-function'

      if (categoryType.category) {
        // Get translated category name using i18n
        // Support both i18n.t and $t methods
        const translateMethod = i18nInstance.t || i18nInstance.$t
        if (translateMethod) {
          category = translateMethod.call(
            i18nInstance,
            `runtimeFormulaTypes.${categoryType.category}`
          )
        }
      }

      const item = {
        name: functionName,
        functionType: FunctionType,
        icon,
        instance,
      }

      if (formulaType === FORMULA_TYPE.OPERATOR) {
        // Store operators by their category
        if (!categorizedOperators[category]) {
          categorizedOperators[category] = []
        }
        categorizedOperators[category].push(item)
      } else if (formulaType === FORMULA_TYPE.FUNCTION) {
        // Store regular functions
        if (!categorizedFunctions[category]) {
          categorizedFunctions[category] = []
        }
        categorizedFunctions[category].push(item)
      }
    } catch (e) {
      // Skip functions that throw errors during processing
      console.warn(`Skipping ${functionName} due to error:`, e.message)
    }
  }

  // Build the hierarchy
  const functionNodes = []
  const categories = Object.keys(categorizedFunctions).sort()

  for (const category of categories) {
    if (categorizedFunctions[category].length > 0) {
      functionNodes.push({
        name: category,
        functions: categorizedFunctions[category].sort((a, b) =>
          a.name.localeCompare(b.name)
        ),
      })
    }
  }

  // Add operators as a separate structure
  const operatorNodes = []
  const operatorCategories = Object.keys(categorizedOperators).sort()

  for (const category of operatorCategories) {
    if (categorizedOperators[category].length > 0) {
      operatorNodes.push({
        name: category,
        operators: categorizedOperators[category].sort((a, b) =>
          a.name.localeCompare(b.name)
        ),
      })
    }
  }

  return { functionNodes, operatorNodes }
}

/**
 * Build function nodes for FormulaInputField
 * @param {Object} app The app instance with registry or Vue component instance
 * @param {Object} i18n The i18n instance (optional, will be extracted from app if not provided)
 * @returns {Array} Array of function nodes ready for FormulaInputField
 */
export const buildFormulaFunctionNodes = (app) => {
  // Support both Option API (this.$t) and Composition API (app.i18n)
  const i18nInstance = app.$i18n
  const { functionNodes, operatorNodes } = getFormulaFunctionsByCategory(
    app,
    i18nInstance
  )
  const nodes = []

  // Get translation methods once at the beginning
  const tMethod = app.$t?.bind(app) || i18nInstance?.t?.bind(i18nInstance)

  // Process regular functions
  if (functionNodes.length > 0) {
    const functionCategories = []

    for (const category of functionNodes) {
      const categoryNodes = []

      for (const func of category.functions) {
        const instance = func.instance

        // Get function signature information
        let signature = null

        // Check if function is variadic
        // A function is variadic if:
        // 1. It has a custom validateNumberOfArgs implementation
        // 2. OR it doesn't have args property (like concat)
        const hasCustomValidation =
          instance.validateNumberOfArgs &&
          instance.validateNumberOfArgs !==
            instance.constructor.prototype.validateNumberOfArgs
        const isVariadic = !instance.args || hasCustomValidation

        // Calculate minArgs by testing validateNumberOfArgs
        let minArgs = 1
        if (instance.validateNumberOfArgs) {
          // Test with increasing numbers of arguments to find the minimum
          for (let testCount = 0; testCount <= 10; testCount++) {
            const testArgs = new Array(testCount).fill({})
            const isValid = instance.validateNumberOfArgs(testArgs)
            if (isValid) {
              // This number of args is valid, this is the minimum
              minArgs = testCount
              break
            }
          }
        } else if (!isVariadic && instance.args) {
          minArgs = instance.numArgs ?? instance.args.length
        }

        if (instance.args && instance.args.length > 0) {
          signature = {
            parameters: instance.args.map((arg, index) => {
              // Map argument types to their string representation
              let type = 'any'
              const argClassName = arg.constructor.name

              if (argClassName === 'NumberBaserowRuntimeFormulaArgumentType') {
                type = 'number'
              } else if (
                argClassName === 'TextBaserowRuntimeFormulaArgumentType'
              ) {
                type = 'text'
              } else if (
                argClassName === 'DateTimeBaserowRuntimeFormulaArgumentType'
              ) {
                type = 'date'
              } else if (
                argClassName === 'ObjectBaserowRuntimeFormulaArgumentType'
              ) {
                type = 'object'
              }

              return {
                type,
                required: true,
              }
            }),
            variadic: isVariadic,
            minArgs,
            maxArgs: isVariadic
              ? null
              : (instance.numArgs ?? instance.args.length),
          }
        } else {
          signature = {
            parameters: [
              {
                type: 'any',
                required: true,
              },
            ],
            variadic: isVariadic,
            minArgs,
            maxArgs: isVariadic ? null : 1,
          }
        }

        // Get description and examples
        let description = null
        let example = null
        try {
          description = instance.getDescription()
        } catch (e) {
          // Method not implemented
        }
        try {
          const examples = instance.getExamples()
          example = examples && examples.length > 0 ? examples[0] : null
        } catch (e) {
          // Method not implemented
        }

        categoryNodes.push({
          name: func.name,
          type: 'function',
          description,
          example,
          highlightingColor: 'blue',
          icon: func.icon,
          identifier: null,
          order: null,
          signature,
        })
      }

      functionCategories.push({
        name: category.name,
        identifier: null,
        order: null,
        signature: null,
        description: null,
        example: null,
        highlightingColor: null,
        icon: null,
        nodes: categoryNodes,
      })
    }

    // Add functions as a top-level section
    nodes.push({
      name: tMethod('runtimeFormulaTypes.formulaTypeFormula', {
        count: functionNodes.length,
      }),
      type: 'function',
      identifier: null,
      order: null,
      signature: null,
      description: null,
      example: null,
      highlightingColor: 'blue',
      icon: null,
      nodes: functionCategories,
    })
  }

  // Process operators
  if (operatorNodes.length > 0) {
    const operatorCategories = []

    for (const category of operatorNodes) {
      const categoryNodes = []

      for (const op of category.operators) {
        const instance = op.instance
        const operatorSymbol = instance.getOperatorSymbol

        // Build operator signature
        const signature = {
          operator: operatorSymbol,
          parameters: instance.args
            ? instance.args.map((arg, index) => {
                // Map argument types to their string representation
                let type = 'any'
                const argClassName = arg.constructor.name

                if (
                  argClassName === 'NumberBaserowRuntimeFormulaArgumentType'
                ) {
                  type = 'number'
                } else if (
                  argClassName === 'TextBaserowRuntimeFormulaArgumentType'
                ) {
                  type = 'text'
                } else if (
                  argClassName === 'DateTimeBaserowRuntimeFormulaArgumentType'
                ) {
                  type = 'date'
                } else if (
                  argClassName === 'ObjectBaserowRuntimeFormulaArgumentType'
                ) {
                  type = 'object'
                }

                return {
                  name: index === 0 ? 'left' : 'right',
                  type,
                  required: true,
                }
              })
            : [
                {
                  type: 'any',
                  required: true,
                },
                {
                  type: 'any',
                  required: true,
                },
              ],
          variadic: false,
          minArgs: 2,
          maxArgs: 2,
        }

        // Get description and examples
        let description = null
        let example = null

        description = instance.getDescription()
        const examples = instance.getExamples()
        example = examples && examples.length > 0 ? examples[0] : null

        categoryNodes.push({
          name: op.name,
          type: 'operator',
          description,
          example,
          highlightingColor: 'green',
          icon: op.icon,
          identifier: null,
          order: null,
          signature,
        })
      }

      operatorCategories.push({
        name: category.name,
        example: null,
        signature: null,
        highlightingColor: null,
        icon: null,
        identifier: null,
        order: null,
        description: null,
        nodes: categoryNodes,
      })
    }

    // Add operators as a top-level section
    nodes.push({
      name: tMethod('runtimeFormulaTypes.formulaTypeOperator', {
        count: operatorNodes.length,
      }),
      type: 'operator',
      nodes: operatorCategories,
    })
  }
  return nodes
}
