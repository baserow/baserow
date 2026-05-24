/**
 * Counts unbalanced (unclosed) opening parentheses in a formula string,
 * ignoring characters inside string literals.
 */
function countUnbalancedParens(text) {
  let depth = 0
  let inString = false
  let quoteChar = null

  for (let i = 0; i < text.length; i++) {
    const ch = text[i]
    if (inString) {
      if (ch === '\\' && i + 1 < text.length) {
        i++ // skip escaped character
        continue
      }
      if (ch === quoteChar) inString = false
      continue
    }
    if (ch === "'" || ch === '"') {
      inString = true
      quoteChar = ch
      continue
    }
    if (ch === '(') depth++
    else if (ch === ')') depth--
  }

  return Math.max(0, depth)
}

/**
 * Removes the last `count` function-closing-paren nodes from a flat
 * content array, along with their trailing ZWS separator. Used to strip
 * the artificial closing parens that were added to make an incomplete
 * formula parseable, so the cursor ends up inside the last open function
 * ready for the user to type its argument.
 */
function stripTrailingClosingParens(nodes, count) {
  const result = [...nodes]

  for (let i = 0; i < count; i++) {
    // Remove trailing ZWS separator that follows the closing paren
    if (
      result.length > 0 &&
      result[result.length - 1].type === 'text' &&
      result[result.length - 1].text === '\u200B'
    ) {
      result.pop()
    }
    // Remove the function-closing-paren itself
    if (
      result.length > 0 &&
      result[result.length - 1].type === 'function-closing-paren'
    ) {
      result.pop()
    } else {
      break
    }
  }

  return result
}

/**
 * Creates a clipboard text serializer for the formula editor
 * @param {Function} toFormula - Function to convert editor content to formula string
 * @returns {Function} Serializer function
 */
export function createClipboardTextSerializer(toFormula) {
  return (slice) => {
    // Serialize the slice to formula text
    const content = {
      type: 'doc',
      content: [{ type: 'wrapper', content: [] }],
    }

    // Extract nodes from the slice
    const nodes = []
    slice.content.forEach((node) => {
      nodes.push(node.toJSON())
    })

    content.content[0].content = nodes

    // Convert to formula string
    const formula = toFormula(content)

    return formula || ''
  }
}

/**
 * Creates a paste handler for the formula editor
 * @param {Object} options - Handler options
 * @param {Function} options.toContent - Function to parse formula string to editor content
 * @param {Function} options.getMode - Function to get current editor mode
 * @returns {Function} Paste handler function
 */
export function createPasteHandler({ toContent, getMode }) {
  return (view, event, slice) => {
    // Only handle paste in advanced mode
    if (getMode() !== 'advanced') {
      return false
    }

    // Get the pasted text
    const text = event.clipboardData.getData('text/plain')
    if (!text) {
      return false
    }

    let wrapperContent = null
    let extraParens = 0

    // First attempt: parse the formula as-is.
    const directContent = toContent(text)
    if (directContent) {
      wrapperContent = directContent.content?.[0]?.content ?? []
    } else {
      // Direct parse failed — the formula is likely incomplete (e.g. a
      // trailing open paren). Count unbalanced parens and complete the
      // formula with the minimum number of closing parens so the parser
      // can produce proper function/group nodes. We then strip those
      // artificial parens from the content before inserting, which leaves
      // the cursor inside the last open function's argument slot. The user
      // can then type the argument and close with `)` normally.
      extraParens = countUnbalancedParens(text)
      if (extraParens > 0) {
        const completedContent = toContent(text + ')'.repeat(extraParens))
        if (completedContent) {
          const raw = completedContent.content?.[0]?.content ?? []
          wrapperContent = stripTrailingClosingParens(raw, extraParens)
        }
      }
    }

    if (!wrapperContent || wrapperContent.length === 0) {
      return false
    }

    try {
      const { tr } = view.state
      const { from, to } = view.state.selection
      const nodes = wrapperContent.map((item) =>
        view.state.schema.nodeFromJSON(item)
      )
      tr.replaceWith(from, to, nodes)
      view.dispatch(tr)
      return true
    } catch (error) {
      console.error('Error inserting pasted formula:', error)
      return false
    }
  }
}
