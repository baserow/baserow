export class FromTipTapVisitor {
  constructor(functions) {
    this.functions = functions
  }

  visit(node) {
    switch (node.type) {
      case 'text':
        return this.visitText(node)
      case 'doc':
        return this.visitDoc(node)
      case 'wrapper':
        return this.visitWrapper(node)
      default:
        return this.visitFunction(node)
    }
  }

  visitDoc(node) {
    if (!node.content || node.content.length === 0) {
      return ''
    }

    const nodeContents = node.content.map(this.visit.bind(this))

    if (nodeContents.length === 1) {
      if (nodeContents[0] === "''") {
        return ''
      } else {
        return nodeContents[0]
      }
    }
    return `concat(${nodeContents.join(", '\n', ")})`
  }

  visitWrapper(node) {
    if (!node.content || node.content.length === 0) {
      return "''"
    }

    if (node.content.length === 1) {
      return this.visit(node.content[0])
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

    return `concat(${node.content.map(this.visit.bind(this)).join(', ')})`
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
      if (node.type === 'text') {
        fullContent += node.text
      } else {
        fullContent += this.visit(node)
      }
    }

    const argsStartIndex = fullContent.indexOf('(')
    const argsEndIndex = fullContent.lastIndexOf(')')

    if (argsStartIndex === -1 || argsEndIndex === -1) {
      return null
    }

    const argsString = fullContent.substring(argsStartIndex + 1, argsEndIndex)

    return `${functionName}(${argsString})`
  }

  visitText(node) {
    const text = node.text.trim()

    const functionCallPattern = /^[a-zA-Z_][a-zA-Z0-9_]*\s*\([^]*\)$/
    const simpleExpressionPattern = /^(\d+(\.\d+)?|true|false|'[^']*'|"[^"]*")$/
    const mathExpressionPattern = /^[\d\s+\-*/().<>=!&|]+$/

    if (functionCallPattern.test(text) || simpleExpressionPattern.test(text)) {
      return text
    }

    if (mathExpressionPattern.test(text)) {
      return text
    }

    return `'${node.text.replace(/'/g, "\\'")}'`
  }

  visitFunction(node) {
    const formulaFunction = Object.values(this.functions.getAll()).find(
      (functionCurrent) => functionCurrent.formulaComponentType === node.type
    )

    return formulaFunction?.fromNodeToFormula(node)
  }
}
