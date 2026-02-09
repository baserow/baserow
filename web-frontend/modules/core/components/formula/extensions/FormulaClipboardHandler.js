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

    // Try to parse it as a formula
    try {
      const content = toContent(text)
      if (!content) {
        return false
      }

      // Get the wrapper content (skip doc and wrapper nodes)
      const wrapperContent =
        content.content && content.content[0] && content.content[0].content
          ? content.content[0].content
          : []

      // Insert the parsed content at the current selection
      if (wrapperContent.length > 0) {
        const { tr } = view.state
        const { from, to } = view.state.selection

        // Create nodes from the content
        const nodes = wrapperContent.map((item) =>
          view.state.schema.nodeFromJSON(item)
        )

        // Replace the selection with the nodes
        tr.replaceWith(from, to, nodes)
        view.dispatch(tr)
        return true
      }
    } catch (error) {
      console.error('Error parsing pasted formula:', error)
      return false
    }

    return false
  }
}
