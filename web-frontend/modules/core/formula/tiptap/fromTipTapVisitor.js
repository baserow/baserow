const ZWS_MARKER = Symbol('zws_marker')

export class FromTipTapVisitor {
  constructor(functions, mode = 'simple') {
    this.functions = functions
    this.mode = mode
  }

  visit(node) {
    switch (node.type) {
      case 'text':
        return this.visitText(node)
      case 'doc':
        return this.visitDoc(node)
      case 'wrapper':
        return this.visitWrapper(node)
      case 'function-formula-component':
        return this.visitFunctionFormulaComponent(node)
      case 'function-argument-comma':
        return ','
      case 'function-closing-paren':
        return ')'
      case 'group-opening-paren':
        return '('
      case 'group-closing-paren':
        return ')'
      case 'operator-formula-component':
        return this.visitOperatorFormulaComponent(node)
      case 'hardBreak':
        return this.visitHardBreak(node)
      default:
        return this.visitFunction(node)
    }
  }

  visitDoc(node) {
    if (!node.content || node.content.length === 0) {
      return ''
    }

    const nodeContents = node.content
      .map(this.visit.bind(this))
      .filter((c) => c !== ZWS_MARKER)

    if (nodeContents.length === 0) {
      return ''
    }

    if (nodeContents.length === 1) {
      if (nodeContents[0] === "''") {
        return ''
      } else {
        return nodeContents[0]
      }
    }

    // Try to reconstruct a single function call spread across multiple wrappers
    const flatContent = node.content.flatMap((w) =>
      Array.isArray(w?.content) ? w.content : []
    )
    if (flatContent.length > 0 && this.isFunctionCallPattern(flatContent)) {
      const result = this.assembleFunctionCall(flatContent)
      if (result) return result
    }

    // Fallback: join multiple paragraphs with a visible newline
    return `concat(${nodeContents.join(", '\n', ")})`
  }

  visitWrapper(node) {
    if (!node.content || node.content.length === 0) {
      return "''"
    }

    // Handle nested empty wrapper
    if (node.content.length === 1 && node.content[0].type === 'wrapper') {
      return this.visit(node.content[0])
    }

    if (node.content.length === 1) {
      const result = this.visit(node.content[0])
      return result === ZWS_MARKER ? "''" : result
    }

    if (this.isFunctionCallPattern(node.content)) {
      const result = this.assembleFunctionCall(node.content)
      if (result) return result
    }

    if (node.content.length >= 3) {
      const firstNode = node.content[0]
      const lastNode = node.content[node.content.length - 1]

      if (firstNode.type === 'text' && lastNode.type === 'text') {
        const firstText = firstNode.text
        const lastText = lastNode.text

        if (
          /^[a-zA-Z_][a-zA-Z0-9_]*\s*\(/.test(firstText) &&
          lastText.includes(')')
        ) {
          const result = this.assembleFunctionCall(node.content)
          if (result) return result
        }
      }
    }

    if (this.mode === 'simple') {
      const parts = node.content
        .map(this.visit.bind(this))
        .filter((p) => p !== ZWS_MARKER)

      if (parts.length === 0) {
        return "''"
      } else if (parts.length === 1) {
        return parts[0]
      } else {
        return `concat(${parts.join(', ')})`
      }
    } else {
      const parts = node.content
        .map(this.visit.bind(this))
        .filter((p) => p !== ZWS_MARKER)
      return parts.join('')
    }
  }

  isFunctionCallPattern(content) {
    if (content.length < 2) return false

    const firstNode = content[0]
    const lastNode = content[content.length - 1]

    if (firstNode.type !== 'text') return false
    const firstText = firstNode.text
    const functionStartPattern = /^[a-zA-Z_][a-zA-Z0-9_]*\s*\(/
    if (!functionStartPattern.test(firstText)) return false

    if (lastNode.type !== 'text') return false
    const lastText = lastNode.text
    if (!lastText.includes(')')) return false

    return true
  }

  assembleFunctionCall(content) {
    const firstNode = content[0]

    const firstText = firstNode.text
    const functionMatch = firstText.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/)
    if (!functionMatch) return null

    const functionName = functionMatch[1]

    let fullContent = ''
    for (let i = 0; i < content.length; i++) {
      const node = content[i]
      fullContent += this.visit(node)
    }

    const argsStartIndex = fullContent.indexOf('(')
    const argsEndIndex = fullContent.lastIndexOf(')')

    if (argsStartIndex === -1 || argsEndIndex === -1) {
      return null
    }

    const argsString = fullContent.substring(argsStartIndex + 1, argsEndIndex)
    const suffix = fullContent.slice(argsEndIndex + 1)
    return `${functionName}(${argsString})${suffix}`
  }

  visitText(node) {
    if (node.text === '\u200B') {
      return ZWS_MARKER
    }
    // Remove zero-width spaces used for cursor positioning
    const cleanText = node.text.replace(/\u200B/g, '')

    if (this.mode === 'simple') {
      return `'${cleanText.replace(/'/g, "\\'")}'`
    }

    // In advanced mode, we need to escape actual newlines in the text
    // to make them valid in string literals
    const cleanTextAdvanced = cleanText.replace(/\n/g, '\n')
    return cleanTextAdvanced
  }

  visitFunction(node) {
    const formulaFunction = Object.values(this.functions.getAll()).find(
      (functionCurrent) => functionCurrent.formulaComponentType === node.type
    )

    return formulaFunction?.fromNodeToFormula(node)
  }

  visitFunctionFormulaComponent(node) {
    const functionName = node.attrs?.functionName || ''
    // Since the function component now only contains name + opening parenthesis,
    // we just return the function name and opening parenthesis.
    // The arguments and closing parenthesis are handled separately as text nodes
    return `${functionName}(`
  }

  visitOperatorFormulaComponent(node) {
    const operatorSymbol = node.attrs?.operatorSymbol || ''
    // Add space after minus operator to distinguish from negative numbers
    if (operatorSymbol === '-') {
      return '- '
    }
    return operatorSymbol
  }

  visitHardBreak(node) {
    if (this.mode === 'advanced') {
      // In advanced mode, hard breaks are literal newlines inside the text
      return '\n'
    } else {
      // In simple mode, hard breaks represent newline strings in concat
      return "'\\n'"
    }
  }
}
