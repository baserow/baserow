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
    return this.mode === 'advanced'
      ? this._wrapForAdvancedMode(result)
      : this._wrapForSimpleMode(result)
  }

  /**
   * Wraps content for advanced mode - flattens all content into a single wrapper
   */
  _wrapForAdvancedMode(result) {
    const content = _.isArray(result) ? result : [result]
    const flatContent = this._flattenContent(content)
    this._ensureStartsWithZWS(flatContent)

    return {
      type: 'doc',
      content: [
        {
          type: 'wrapper',
          content: flatContent,
        },
      ],
    }
  }

  /**
   * Wraps content for simple mode - preserves wrapper structure or creates one
   */
  _wrapForSimpleMode(result) {
    if (Array.isArray(result)) {
      return this._isArrayOfWrappers(result)
        ? { type: 'doc', content: result }
        : { type: 'doc', content: [{ type: 'wrapper', content: result }] }
    }

    if (result?.type === 'wrapper') {
      return { type: 'doc', content: [result] }
    }

    return {
      type: 'doc',
      content: [{ type: 'wrapper', content: [result] }],
    }
  }

  /**
   * Flattens nested content, extracting items from wrappers and arrays
   */
  _flattenContent(content) {
    return content.flatMap((item) => {
      if (!item) return []
      if (Array.isArray(item)) return item
      if (item.type === 'wrapper' && item.content) return item.content
      return item.type ? [item] : []
    })
  }

  /**
   * Ensures the content array starts with a Zero-Width Space text node
   */
  _ensureStartsWithZWS(content) {
    const firstNode = content[0]
    if (
      !firstNode ||
      firstNode.type !== 'text' ||
      firstNode.text !== '\u200B'
    ) {
      content.unshift({ type: 'text', text: '\u200B' })
    }
  }

  /**
   * Checks if an array contains only wrapper nodes
   */
  _isArrayOfWrappers(array) {
    return array.every((item) => item?.type === 'wrapper')
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
    const innerContent = ctx.expr().accept(this)

    // In advanced mode, wrap the content with group parenthesis nodes
    if (this.mode === 'advanced') {
      const content = []

      // Add opening group parenthesis
      content.push({ type: 'text', text: '\u200B' })
      content.push({ type: 'group-opening-paren' })
      content.push({ type: 'text', text: '\u200B' })

      // Add the inner content
      if (Array.isArray(innerContent)) {
        content.push(...innerContent)
      } else {
        content.push(innerContent)
      }

      // Add closing group parenthesis
      content.push({ type: 'text', text: '\u200B' })
      content.push({ type: 'group-closing-paren' })
      content.push({ type: 'text', text: '\u200B' })

      return content
    }

    // In simple mode, just return the inner content without parentheses
    return innerContent
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

  /**
   * Helper to process text arguments - adds quotes if needed in simple mode
   */
  processTextArg(arg) {
    if (arg.type === 'text' && typeof arg.text === 'string') {
      const isBoolean = arg.text === 'true' || arg.text === 'false'
      const isNumber = !isNaN(Number(arg.text))
      const hasQuotes =
        arg.text.length >= 2 &&
        ((arg.text.startsWith('"') && arg.text.endsWith('"')) ||
          (arg.text.startsWith("'") && arg.text.endsWith("'")))

      if (isBoolean || isNumber || hasQuotes) {
        return arg
      } else {
        // In simple mode, add quotes
        return { type: 'text', text: `"${arg.text}"` }
      }
    }
    return arg
  }

  /**
   * Adds an argument to content array, spreading if it's an array
   */
  addArgToContent(content, arg) {
    if (Array.isArray(arg)) {
      content.push(...arg)
    } else if (arg) {
      content.push(arg)
    }
  }

  /**
   * Builds content for binary operators (arg1 operator arg2)
   */
  buildOperatorContent(leftArg, rightArg, operatorSymbol) {
    const content = []

    // Add left argument
    const processedLeftArg = this.processTextArg(leftArg)
    this.addArgToContent(content, processedLeftArg)

    // Add operator
    if (this.mode === 'advanced') {
      content.push({
        type: 'operator-formula-component',
        attrs: { operatorSymbol },
      })
      // Add space after minus operator to distinguish from negative numbers
      if (operatorSymbol === '-') {
        content.push({ type: 'text', text: ' ' })
      }
    } else {
      content.push({ type: 'text', text: operatorSymbol })
    }

    // Add right argument
    const processedRightArg = this.processTextArg(rightArg)
    this.addArgToContent(content, processedRightArg)

    return content
  }

  /**
   * Builds content for functions in advanced mode
   */
  buildFunctionContentAdvanced(functionName, args) {
    const result = [
      { type: 'text', text: '\u200B' },
      {
        type: 'function-formula-component',
        attrs: {
          functionName,
          hasNoArgs: args.length === 0,
        },
      },
    ]

    // Add arguments
    args.forEach((arg, index) => {
      if (index > 0) {
        result.push({ type: 'function-argument-comma' })
      }
      this.addArgToContent(result, arg)
    })

    // Add closing parenthesis
    result.push({
      type: 'function-closing-paren',
      attrs: { noArgs: args.length === 0 },
    })

    result.push({ type: 'text', text: '\u200B' })

    return result
  }

  /**
   * Builds content for functions in simple mode
   */
  buildFunctionContentSimple(functionName, args) {
    const content = [{ type: 'text', text: `${functionName}(` }]

    args.forEach((arg, index) => {
      if (index > 0) {
        content.push({ type: 'text', text: ', ' })
      }

      const processedArg = this.processTextArg(arg)
      this.addArgToContent(content, processedArg)
    })

    content.push({ type: 'text', text: ')' })
    return content
  }

  doFunc(functionArgumentExpressions, functionName) {
    const args = Array.from(functionArgumentExpressions, (expr) =>
      expr.accept(this)
    )

    // Preprocess arguments (special handling for 'get' in advanced mode)
    const processedArgs = this.preprocessGetArgs(args, functionName)

    // Get the node from the runtime function
    const formulaFunctionType = this.functions.get(functionName)
    const node = formulaFunctionType.toNode(processedArgs, this.mode)

    // Early return: if it's a component that needs ZWS wrapping
    if (
      node?.type === 'get-formula-component' ||
      node?.type === 'function-formula-component'
    ) {
      return [
        { type: 'text', text: '\u200B' },
        node,
        { type: 'text', text: '\u200B' },
      ]
    }

    // Early return: if it's already an array (e.g., concat with newlines)
    if (Array.isArray(node)) {
      return node
    }

    // Flatten nested arrays in wrapper content
    if (node?.type === 'wrapper' && node.content) {
      node.content = node.content.flat()
      return node
    }

    // Early return: if node is valid, use it
    if (node?.type) {
      return node
    }

    // Fallback: build content manually when no proper TipTap component exists
    return this.buildFallbackContent(args, functionName, formulaFunctionType)
  }

  /**
   * Preprocesses arguments for 'get' function in advanced mode
   */
  preprocessGetArgs(args, functionName) {
    if (functionName === 'get' && this.mode === 'advanced') {
      return args.map((arg) => {
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
    }
    return args
  }

  /**
   * Builds fallback content when function doesn't have a TipTap component
   */
  buildFallbackContent(args, functionName, formulaFunctionType) {
    const isOperator = formulaFunctionType.getOperatorSymbol

    // Handle binary operators
    if (isOperator && args.length === 2) {
      const [leftArg, rightArg] = args
      const content = this.buildOperatorContent(
        leftArg,
        rightArg,
        formulaFunctionType.getOperatorSymbol
      )

      return this.mode === 'advanced' ? content : { type: 'wrapper', content }
    }

    // Handle functions
    const content =
      this.mode === 'advanced'
        ? this.buildFunctionContentAdvanced(functionName, args)
        : this.buildFunctionContentSimple(functionName, args)

    return this.mode === 'advanced' ? content : { type: 'wrapper', content }
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
