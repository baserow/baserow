import BaserowFormulaVisitor from '@baserow/modules/core/formula/parser/generated/BaserowFormulaVisitor'
import { UnknownOperatorError } from '@baserow/modules/core/formula/parser/errors'
import _ from 'lodash'

export class ToTipTapVisitor extends BaserowFormulaVisitor {
  constructor(functions, mode = 'simple') {
    super()
    this.functions = functions
    this.mode = mode
  }

  visitRoot(ctx) {
    const result = ctx.expr().accept(this)

    // In advanced mode, ensure all content is wrapped in a single wrapper
    if (this.mode === 'advanced') {
      const content = _.isArray(result) ? result : [result]
      return {
        type: 'doc',
        content: [
          {
            type: 'wrapper',
            content: content.flatMap((item) => {
              // Filter out null or undefined items
              if (!item) return []

              // If the item is an array (from functions without wrapper in advanced mode)
              if (Array.isArray(item)) {
                return item
              }

              // If the item is a wrapper, extract its content
              if (item.type === 'wrapper' && item.content) {
                return item.content
              }

              // Return the item if it has a type
              return item.type ? [item] : []
            }),
          },
        ],
      }
    }

    return { type: 'doc', content: _.isArray(result) ? result : [result] }
  }

  visitStringLiteral(ctx) {
    switch (ctx.getText()) {
      case "'\n'":
        // Specific element that helps to recognize root concat
        if (this.mode === 'simple') {
          return { type: 'newLine' }
        } else {
          return { type: 'text', text: "'\n'" }
        }
      default: {
        if (this.mode === 'advanced') {
          // In advanced mode, keep quotes for display
          const fullText = ctx.getText()

          // Check if the string contains escaped newlines (\n)
          // If so, split it into text nodes and hardBreak nodes
          if (fullText.includes('\\n')) {
            const quote = fullText[0] // Get the opening quote
            const content = fullText.slice(1, -1) // Remove quotes
            const parts = content.split('\\n')

            // Create an array of text and hardBreak nodes
            const nodes = []
            parts.forEach((part, index) => {
              if (index === 0) {
                // First part: add opening quote
                nodes.push({ type: 'text', text: quote + part })
              } else if (index === parts.length - 1) {
                // Last part: add closing quote
                nodes.push({ type: 'text', text: part + quote })
              } else {
                // Middle parts: no quotes
                nodes.push({ type: 'text', text: part })
              }

              // Add hardBreak between parts (but not after the last one)
              if (index < parts.length - 1) {
                nodes.push({ type: 'hardBreak' })
              }
            })

            return nodes
          }

          return { type: 'text', text: fullText }
        }
        // In simple mode, remove quotes (they will be added back by fromTipTapVisitor)
        const processedString = this.processString(ctx)
        if (processedString) {
          return { type: 'text', text: processedString }
        } else {
          // Empty strings are represented as a special marker that won't be confused with line breaks
          return { type: 'text', text: '\u200B' } // Zero-width space for empty strings
        }
      }
    }
  }

  visitDecimalLiteral(ctx) {
    return { type: 'text', text: ctx.getText() }
  }

  visitBooleanLiteral(ctx) {
    const value = ctx.TRUE() !== null ? 'true' : 'false'
    return { type: 'text', text: value }
  }

  visitBrackets(ctx) {
    // TODO
    return ctx.expr().accept(this)
  }

  processString(ctx) {
    const literalWithoutOuterQuotes = ctx.getText().slice(1, -1)
    let literal

    if (ctx.SINGLEQ_STRING_LITERAL() !== null) {
      literal = literalWithoutOuterQuotes.replace(/\\'/g, "'")
    } else {
      literal = literalWithoutOuterQuotes.replace(/\\"/g, '"')
    }

    return literal
  }

  visitFunctionCall(ctx) {
    const functionName = this.visitFuncName(ctx.func_name()).toLowerCase()
    const functionArgumentExpressions = ctx.expr()

    return this.doFunc(functionArgumentExpressions, functionName)
  }

  doFunc(functionArgumentExpressions, functionName) {
    const args = Array.from(functionArgumentExpressions, (expr) =>
      expr.accept(this)
    )

    // Special handling for 'get' function in advanced mode
    // Remove quotes from the path argument since get expects raw path
    const processedArgs =
      functionName === 'get' && this.mode === 'advanced'
        ? args.map((arg) => {
            if (arg.type === 'text' && arg.text) {
              let text = arg.text
              // Remove quotes if present
              if (
                text.length >= 2 &&
                ((text.startsWith('"') && text.endsWith('"')) ||
                  (text.startsWith("'") && text.endsWith("'")))
              ) {
                text = text.slice(1, -1)
              }
              return { ...arg, text }
            }
            return arg
          })
        : args

    const formulaFunctionType = this.functions.get(functionName)
    const node = formulaFunctionType.toNode(processedArgs, this.mode)

    // If the function returns an array (like concat with newlines in simple mode),
    // return it directly
    if (Array.isArray(node)) {
      return node
    }

    // If the function doesn't have a proper TipTap component (node is null or type is null),
    // wrap it as text but preserve the arguments
    if (!node || !node.type) {
      const content = []

      // Check if this is an operator and should use symbol instead of function name
      const isOperator = formulaFunctionType.getOperatorSymbol

      if (isOperator && args.length === 2) {
        // For binary operators, display as: arg1 symbol arg2
        const [leftArg, rightArg] = args

        // Add left argument
        if (leftArg.type === 'text' && typeof leftArg.text === 'string') {
          const isBoolean = leftArg.text === 'true' || leftArg.text === 'false'
          const isNumber = !isNaN(Number(leftArg.text))
          if (isBoolean || isNumber) {
            content.push(leftArg)
          } else {
            content.push({ type: 'text', text: `"${leftArg.text}"` })
          }
        } else if (Array.isArray(leftArg)) {
          // If arg is an array (from nested function calls in advanced mode),
          // spread its elements
          content.push(...leftArg)
        } else if (leftArg) {
          content.push(leftArg)
        }

        // Add space before operator
        content.push({
          type: 'text',
          text: ' ',
        })

        // Add operator symbol as a component in advanced mode, as text in simple mode
        if (this.mode === 'advanced') {
          content.push({
            type: 'operator-formula-component',
            attrs: {
              operatorSymbol: formulaFunctionType.getOperatorSymbol,
            },
          })
        } else {
          content.push({
            type: 'text',
            text: formulaFunctionType.getOperatorSymbol,
          })
        }

        // Add space after operator
        content.push({
          type: 'text',
          text: ' ',
        })

        // Add right argument
        if (rightArg.type === 'text' && typeof rightArg.text === 'string') {
          const isBoolean =
            rightArg.text === 'true' || rightArg.text === 'false'
          const isNumber = !isNaN(Number(rightArg.text))
          if (isBoolean || isNumber) {
            content.push(rightArg)
          } else {
            content.push({ type: 'text', text: `"${rightArg.text}"` })
          }
        } else if (Array.isArray(rightArg)) {
          // If arg is an array (from nested function calls in advanced mode),
          // spread its elements
          content.push(...rightArg)
        } else if (rightArg) {
          content.push(rightArg)
        }
      } else if (this.mode === 'advanced') {
        // For functions in advanced mode, use the function component
        // Create function component node (just name + opening parenthesis)
        const functionNode = {
          type: 'function-formula-component',
          attrs: {
            functionName,
          },
        }

        // Build the content array with function node + arguments + closing parenthesis
        const result = [functionNode]

        // Add arguments as plain text nodes
        args.forEach((arg, index) => {
          if (index > 0) {
            // Add atomic comma node
            result.push({ type: 'function-argument-comma' })
          }

          // Add the argument directly
          if (Array.isArray(arg)) {
            // If arg is an array (from nested function calls in advanced mode),
            // spread its elements
            result.push(...arg)
          } else if (arg) {
            result.push(arg)
          }
        })

        // Add closing parenthesis as atomic node
        result.push({ type: 'function-closing-paren' })

        return result
      } else {
        // For functions, display as: functionName(arg1, arg2, ...)
        content.push({ type: 'text', text: `${functionName}(` })

        args.forEach((arg, index) => {
          if (index > 0) {
            content.push({ type: 'text', text: ', ' })
          }

          // Check if the argument is a complex node or a simple value
          if (arg.type === 'text' && typeof arg.text === 'string') {
            // Don't add quotes for boolean or numeric values
            const isBoolean = arg.text === 'true' || arg.text === 'false'
            const isNumber = !isNaN(Number(arg.text))

            if (isBoolean || isNumber) {
              content.push(arg)
            } else {
              // For actual string literals, add quotes
              content.push({ type: 'text', text: `"${arg.text}"` })
            }
          } else if (Array.isArray(arg)) {
            // If arg is an array (from nested function calls in advanced mode),
            // spread its elements
            content.push(...arg)
          } else if (arg) {
            content.push(arg)
          }
        })

        content.push({ type: 'text', text: ')' })
      }

      // In advanced mode, return inline content without wrapper
      if (this.mode === 'advanced') {
        return content
      }

      return {
        type: 'wrapper',
        content,
      }
    }

    return node
  }

  visitBinaryOp(ctx) {
    // TODO
    let op

    if (ctx.PLUS()) {
      op = 'add'
    } else if (ctx.MINUS()) {
      op = 'minus'
    } else if (ctx.SLASH()) {
      op = 'divide'
    } else if (ctx.EQUAL()) {
      op = 'equal'
    } else if (ctx.BANG_EQUAL()) {
      op = 'not_equal'
    } else if (ctx.STAR()) {
      op = 'multiply'
    } else if (ctx.GT()) {
      op = 'greater_than'
    } else if (ctx.LT()) {
      op = 'less_than'
    } else if (ctx.GTE()) {
      op = 'greater_than_or_equal'
    } else if (ctx.LTE()) {
      op = 'less_than_or_equal'
    } else if (ctx.AMP_AMP()) {
      op = 'and'
    } else if (ctx.PIPE_PIPE()) {
      op = 'or'
    } else {
      throw new UnknownOperatorError(ctx.getText())
    }

    return this.doFunc(ctx.expr(), op)
  }

  visitFuncName(ctx) {
    // TODO
    return ctx.getText()
  }

  visitIdentifier(ctx) {
    // TODO
    return ctx.getText()
  }

  visitIntegerLiteral(ctx) {
    return { type: 'text', text: ctx.getText() }
  }

  visitLeftWhitespaceOrComments(ctx) {
    // TODO
    return ctx.expr().accept(this)
  }

  visitRightWhitespaceOrComments(ctx) {
    // TODO
    return ctx.expr().accept(this)
  }
}
