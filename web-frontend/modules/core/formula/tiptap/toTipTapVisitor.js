import BaserowFormulaVisitor from '@baserow/modules/core/formula/parser/generated/BaserowFormulaVisitor'
import { UnknownOperatorError } from '@baserow/modules/core/formula/parser/errors'
import _ from 'lodash'
import {
  ZWS,
  zwsTextJSON,
} from '@baserow/modules/core/components/formula/extensions/helpers'

/**
 * Returns true when the ANTLR node is absent or was injected by error
 * recovery (e.g. `<missing ')'>`). The `FormulaInputField` parses formulas
 * in tolerant mode so a partial AST can be rendered while the user is still
 * typing/pasting; this helper lets the visitor degrade gracefully.
 */
const isErrorOrMissingNode = (node) => {
  if (!node) return true
  if (typeof node.isErrorNode === 'function' && node.isErrorNode()) return true
  const text = node.getText?.()
  return Boolean(text && text.startsWith('<missing'))
}

/** Character-stream start index for a rule context or terminal node. */
const startIndexOf = (node) => node?.start?.start ?? node?.symbol?.start ?? -1

/** Character-stream stop index for a rule context or terminal node. */
const stopIndexOf = (node) => node?.stop?.stop ?? node?.symbol?.stop ?? -1

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
    if (!firstNode || firstNode.type !== 'text' || firstNode.text !== ZWS) {
      content.unshift(zwsTextJSON())
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
          return zwsTextJSON() // Zero-width space for empty strings
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

    // In simple mode, parentheses are implicit — just return the inner content.
    if (this.mode !== 'advanced') {
      return innerContent
    }

    const content = [
      zwsTextJSON(),
      { type: 'group-opening-paren' },
      zwsTextJSON(),
    ]

    if (Array.isArray(innerContent)) {
      content.push(...innerContent)
    } else if (innerContent) {
      content.push(innerContent)
    }

    // Skip the closing paren node when it was synthesized by error recovery,
    // so the rest of the formula can keep highlighting normally.
    if (!isErrorOrMissingNode(ctx.CLOSE_PAREN())) {
      content.push(
        zwsTextJSON(),
        { type: 'group-closing-paren' },
        zwsTextJSON()
      )
    }

    return content
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

    // Tolerant paths: when a parenthesis was synthesized by error recovery
    // (e.g. bare `month` or unclosed `month(` pasted into the editor), render
    // the already-parsed prefix as plain text and splice whatever comes next
    // straight from the source so surrounding operators are not dropped.
    if (isErrorOrMissingNode(ctx.OPEN_PAREN())) {
      return this._renderPartialCall(ctx, ctx.func_name(), functionName)
    }
    if (isErrorOrMissingNode(ctx.CLOSE_PAREN())) {
      return this._renderPartialCall(ctx, ctx.OPEN_PAREN(), `${functionName}(`)
    }

    return this.doFunc(ctx.expr(), functionName)
  }

  /**
   * Emits `prefixText` for the portion of the call that was already parsed
   * (`func_name` or `func_name(`), then walks the remaining children while
   * splicing any raw source the parser dropped during error recovery (for
   * instance the `+` in `month + year(...)`). The gap text is read directly
   * from the input stream since those tokens are no longer in the AST.
   */
  _renderPartialCall(ctx, prefixNode, prefixText) {
    const parts = [{ type: 'text', text: prefixText }]
    const inputStream = ctx.start?.getInputStream?.() ?? null
    const funcNameNode = ctx.func_name()
    let lastStopIndex = stopIndexOf(prefixNode)

    const pushGap = (from, to) => {
      if (!inputStream || from < 0 || to < from) return
      const gapText = inputStream.getText(from, to)
      if (gapText && !gapText.includes('<missing')) {
        parts.push({ type: 'text', text: gapText })
      }
    }

    for (const child of ctx.children ?? []) {
      if (child === prefixNode || child === funcNameNode) continue
      const childText = child.getText?.()
      if (childText?.startsWith('<missing')) continue

      pushGap(lastStopIndex + 1, startIndexOf(child) - 1)

      try {
        const result = child.accept(this)
        if (Array.isArray(result)) parts.push(...result)
        else if (result) parts.push(result)
      } catch (e) {
        if (childText) parts.push({ type: 'text', text: childText })
      }

      lastStopIndex = Math.max(lastStopIndex, stopIndexOf(child))
    }

    pushGap(lastStopIndex + 1, stopIndexOf(ctx))
    return parts
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

      if (isBoolean || isNumber || hasQuotes || this.mode === 'advanced') {
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
      zwsTextJSON(),
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

    result.push(zwsTextJSON())

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
    // Each argument is visited independently so a single broken sub-expression
    // in a tolerant parse does not take the whole formula down with it.
    const args = Array.from(functionArgumentExpressions, (expr) => {
      try {
        return expr.accept(this)
      } catch (e) {
        return { type: 'text', text: expr.getText() }
      }
    })

    const formulaFunctionType = this.functions.get(functionName)
    if (!formulaFunctionType) {
      // Unknown function in a partial AST — render as plain text so the rest
      // of the formula can keep highlighting normally.
      const argsText = args.map((a) => a?.text ?? '').join(', ')
      return { type: 'text', text: `${functionName}(${argsText})` }
    }

    const processedArgs = this.preprocessGetArgs(args, functionName)

    let node
    try {
      node = formulaFunctionType.toNode(processedArgs, this.mode)
    } catch (e) {
      return this.buildFallbackContent(args, functionName, formulaFunctionType)
    }

    if (
      node?.type === 'get-formula-component' ||
      node?.type === 'function-formula-component'
    ) {
      return [zwsTextJSON(), node, zwsTextJSON()]
    }
    if (Array.isArray(node)) {
      return node
    }
    if (node?.type === 'wrapper' && node.content) {
      node.content = node.content.flat()
      return node
    }
    if (node?.type) {
      return node
    }

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
