import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import parseBaserowFormula from '@baserow/modules/core/formula/parser/parser'

const formulaValidationPluginKey = new PluginKey('formulaValidation')

/**
 * @name FormulaValidationExtension
 * @description A Tiptap extension that provides real-time validation for Baserow
 * formulas as the user types. It hooks into the editor's update cycle to parse
 * the formula, check for syntax errors, and validate function arguments against
 * their registered signatures (e.g., argument count and type compatibility).
 * The validation status and any errors are communicated back to the parent Vue
 * component via the `validation-changed` event.
 */
export const FormulaValidationExtension = Extension.create({
  name: 'formulaValidation',

  addOptions() {
    return {
      functionSignatures: {},
      dataProviders: [],
      applicationContext: {},
      vueComponent: null,
    }
  },

  addStorage() {
    return {
      isFormulaInvalid: false,
      validationErrors: [],
    }
  },

  addProseMirrorPlugins() {
    const {
      functionSignatures,
      dataProviders,
      applicationContext,
      vueComponent,
    } = this.options

    const getExpressionType = (expr) => {
      if (!expr) return 'unknown'

      try {
        const exprText = expr.getText().trim()

        if (
          (exprText.startsWith("'") && exprText.endsWith("'")) ||
          (exprText.startsWith('"') && exprText.endsWith('"'))
        ) {
          return 'text'
        }

        if (/^-?\d+(\.\d+)?$/.test(exprText)) {
          return 'number'
        }

        if (exprText === 'true' || exprText === 'false') {
          return 'boolean'
        }

        if (expr.constructor.name === 'FunctionCallContext') {
          const funcName = expr.func_name().getText().toLowerCase()

          const systemFunctions = ['get']
          if (systemFunctions.includes(funcName)) {
            if (funcName === 'get') {
              const type = getTypeFromDataProviders(expr)
              return type
            }
            return 'any'
          }

          const funcSignature = functionSignatures[funcName]
          return funcSignature?.returnType || 'any'
        }

        if (expr.constructor.name === 'FieldReferenceContext') {
          return 'any'
        }

        if (expr.constructor.name === 'BinaryOpContext') {
          if (
            expr.PLUS?.() ||
            expr.MINUS?.() ||
            expr.STAR?.() ||
            expr.SLASH?.()
          ) {
            return 'number'
          }
          if (
            expr.GT?.() ||
            expr.LT?.() ||
            expr.GTE?.() ||
            expr.LTE?.() ||
            expr.EQUAL?.() ||
            expr.BANG_EQUAL?.() ||
            expr.AMP_AMP?.() ||
            expr.PIPE_PIPE?.()
          ) {
            return 'boolean'
          }

          return 'unknown'
        }

        if (expr.constructor.name === 'ParenthesizedExprContext') {
          const innerExpr = expr.expr()
          if (innerExpr) {
            return getExpressionType(innerExpr)
          }
        }

        return 'any'
      } catch (error) {
        return 'unknown'
      }
    }

    const isTypeCompatible = (actualType, expectedType) => {
      if (expectedType === 'any' || actualType === 'any') return true
      if (actualType === 'unknown' && expectedType !== 'unknown') {
        return false
      }
      return actualType === expectedType
    }

    const getTypeFromDataProviders = (expr) => {
      const args = expr.expr() || []
      if (args.length === 0) return 'unknown'

      const pathArg = args[0]
      const pathText = pathArg.getText().trim()

      let path = pathText
      if (
        (path.startsWith("'") && path.endsWith("'")) ||
        (path.startsWith('"') && path.endsWith('"'))
      ) {
        path = path.slice(1, -1)
      }

      return getDataExplorerVariableType(path)
    }

    const getDataExplorerVariableType = (path) => {
      try {
        const pathParts = path.split('.')

        if (pathParts.length === 0) return 'unknown'

        const currentDataProviders =
          vueComponent?.dataProviders || dataProviders
        const currentApplicationContext =
          vueComponent?.applicationContext || applicationContext

        const providerType = pathParts[0]
        const dataProvider = currentDataProviders?.find(
          (provider) => provider.type === providerType
        )

        if (!dataProvider) {
          return 'unknown'
        }

        const rootNode = dataProvider.getNodes(currentApplicationContext)

        if (!rootNode) {
          return 'unknown'
        }

        if (pathParts.length === 1 && rootNode.identifier === pathParts[0]) {
          return mapDataExplorerTypeToFormulaType(rootNode.type)
        }

        if (pathParts.length > 1) {
          if (!rootNode.nodes || !Array.isArray(rootNode.nodes)) {
            return 'unknown'
          }

          const fieldIdentifier = pathParts[1]
          const foundNode = rootNode.nodes.find(
            (node) => node.identifier === fieldIdentifier
          )

          if (!foundNode) {
            return 'unknown'
          }

          const nodeType = foundNode.type
          return mapDataExplorerTypeToFormulaType(nodeType)
        }

        return 'unknown'
      } catch (error) {
        console.error('Error resolving DataExplorer variable type:', error)
        return 'unknown'
      }
    }

    const mapDataExplorerTypeToFormulaType = (dataExplorerType) => {
      const typeMap = {
        text: 'text',
        string: 'text',
        number: 'number',
        integer: 'number',
        float: 'number',
        boolean: 'boolean',
        date: 'text',
        datetime: 'text',
        email: 'text',
        url: 'text',
        array: 'text',
        object: 'text',
      }

      return typeMap[dataExplorerType] || 'text'
    }

    const validateFunctionArguments = (tree) => {
      let hasErrors = false

      const systemFunctions = ['get']

      const validateNode = (node) => {
        if (node.constructor.name === 'FunctionCallContext') {
          const functionName = node.func_name().getText().toLowerCase()
          const args = node.expr() || []

          if (systemFunctions.includes(functionName)) {
            return
          }

          const signature = functionSignatures[functionName]

          if (signature) {
            const argCount = args.length

            if (argCount < signature.minArgs) {
              hasErrors = true
              return
            }

            if (!signature.hasUnlimitedArgs && argCount > signature.maxArgs) {
              hasErrors = true
              return
            }

            if (signature.parameters && signature.parameters.length > 0) {
              const requiredParams = signature.parameters.filter(
                (p) => p.required
              )
              if (argCount < requiredParams.length) {
                hasErrors = true
                return
              }

              for (
                let i = 0;
                i < argCount && i < signature.parameters.length;
                i++
              ) {
                const param = signature.parameters[i]
                const arg = args[i]

                if (param && arg) {
                  const actualType = getExpressionType(arg)
                  const expectedType = param.type

                  if (!isTypeCompatible(actualType, expectedType)) {
                    hasErrors = true
                    return
                  }
                }
              }

              if (
                signature.variadic &&
                argCount > signature.parameters.length
              ) {
                const lastParam =
                  signature.parameters[signature.parameters.length - 1]
                if (lastParam) {
                  for (let i = signature.parameters.length; i < argCount; i++) {
                    const arg = args[i]
                    const actualType = getExpressionType(arg)
                    const expectedType = lastParam.type

                    if (!isTypeCompatible(actualType, expectedType)) {
                      hasErrors = true
                      return
                    }
                  }
                }
              }
            }
          } else {
            hasErrors = true
            return
          }
        }

        if (node.constructor.name === 'BinaryOpContext') {
          const expressions = node.expr() || []

          if (expressions.length < 2) {
            hasErrors = true
            return
          }
        }

        if (!hasErrors && node.children && node.children.length > 0) {
          node.children.forEach((child) => {
            if (child && typeof child === 'object' && child.constructor) {
              validateNode(child)
            }
          })
        }
      }

      validateNode(tree)

      return hasErrors
    }

    const validateCurrentFormula = (editor) => {
      let formulaText = null

      try {
        if (vueComponent && vueComponent.toFormula) {
          formulaText = vueComponent.toFormula(editor.getJSON())
        } else {
          formulaText = editor.state.doc.textContent
        }
      } catch (error) {
        console.warn('Error getting formula from editor:', error)
        formulaText = editor.state.doc.textContent
      }

      if (!formulaText) {
        this.storage.isFormulaInvalid = false
        this.storage.validationErrors = []

        if (vueComponent) {
          vueComponent.$emit('validation-changed', {
            isValid: true,
            errors: [],
          })
        }
        return
      }

      try {
        const tree = parseBaserowFormula(formulaText)
        const hasValidationErrors = validateFunctionArguments(tree)

        this.storage.isFormulaInvalid = hasValidationErrors
        this.storage.validationErrors = hasValidationErrors
          ? ['Validation errors found']
          : []

        if (vueComponent) {
          vueComponent.$emit('validation-changed', {
            isValid: !hasValidationErrors,
            errors: this.storage.validationErrors,
          })
        }
      } catch (error) {
        this.storage.isFormulaInvalid = true
        this.storage.validationErrors = ['Parse error: ' + error.message]

        if (vueComponent) {
          vueComponent.$emit('validation-changed', {
            isValid: false,
            errors: this.storage.validationErrors,
          })
        }
      }
    }

    return [
      new Plugin({
        key: formulaValidationPluginKey,
        state: {
          init: () => ({}),
          apply: (transaction, state) => {
            if (transaction.docChanged) {
              setTimeout(() => {
                const editor = this.editor
                if (editor) {
                  validateCurrentFormula(editor)
                }
              }, 0)
            }
            return state
          },
        },
      }),
    ]
  },
})
