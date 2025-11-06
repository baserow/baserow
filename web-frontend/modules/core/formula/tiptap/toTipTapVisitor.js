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
        return { type: 'newLine' }
      default: {
        const processedString = this.processString(ctx)
        if (processedString) {
          return { type: 'text', text: processedString }
        } else {
          // An empty string is an empty wrapper
          return { type: 'wrapper' }
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

    const formulaFunctionType = this.functions.get(functionName)
    const node = formulaFunctionType.toNode(args, this.mode)

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

        // Add operator symbol
        content.push({
          type: 'text',
          text: ` ${formulaFunctionType.getOperatorSymbol} `,
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
