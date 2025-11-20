import { Extension } from '@tiptap/core'
import { Plugin, PluginKey, TextSelection } from '@tiptap/pm/state'
import { Fragment } from '@tiptap/pm/model'

export const OperatorDetectionExtension = Extension.create({
  name: 'operatorDetection',

  addOptions() {
    return {
      operators: [],
      vueComponent: null,
    }
  },

  addProseMirrorPlugins() {
    const operators = this.options.operators

    function isInsideStringLiteral(doc, pos) {
      const text = doc.textBetween(0, pos, '\n')
      let inString = false
      let quoteChar = null

      for (let i = 0; i < text.length; i++) {
        const char = text[i]
        if ((char === '"' || char === "'") && text[i - 1] !== '\\') {
          if (!inString) {
            inString = true
            quoteChar = char
          } else if (char === quoteChar) {
            inString = false
            quoteChar = null
          }
        }
      }

      return inString
    }

    function shouldConvertOperator(view, from, to, typedChar) {
      const { state } = view
      const { doc } = state

      // Don't convert if inside a string literal
      if (isInsideStringLiteral(doc, from)) {
        return false
      }

      return true
    }

    function handleOperatorTyped(view, from, to, typedText) {
      const { state } = view
      const { tr, schema } = state

      let operatorText = typedText
      let startPos = from
      let endPos = from

      // Unified handling for all compound operators (!=, >=, <=, &&, ||)
      // Try to form a compound operator by looking at what's before the cursor

      // First, check if there's an operator node right before the cursor
      // This has priority because > and < are converted to nodes immediately
      const $pos = state.doc.resolve(from)
      const nodeBefore = $pos.nodeBefore

      if (nodeBefore && nodeBefore.type.name === 'operator-formula-component') {
        const prevOperator = nodeBefore.attrs.operatorSymbol
        const potentialFromNode = prevOperator + typedText

        if (operators.includes(potentialFromNode)) {
          // Replace the previous operator node with the compound operator
          operatorText = potentialFromNode
          startPos = from - nodeBefore.nodeSize
          endPos = from
        }
      } else {
        // Check for text character before cursor
        const prevChar = state.doc.textBetween(Math.max(0, from - 1), from, '')
        const potentialOperator = prevChar + typedText

        if (prevChar && operators.includes(potentialOperator)) {
          // We can form a compound operator with the previous character
          // Only if there actually IS a previous character
          operatorText = potentialOperator
          startPos = from - 1
          endPos = from
        } else if (operators.includes(typedText)) {
          // Simple operator (like > or <), no need to look back
          operatorText = typedText
          // startPos and endPos already set to 'from'
        }
      }

      // Check if the operator is in the allowed list
      if (!operators.includes(operatorText)) {
        return false
      }

      // Create operator node
      const operatorNode = schema.nodes['operator-formula-component'].create({
        operatorSymbol: operatorText,
      })

      // Create the fragment with just the operator node (no spaces)
      const fragment = Fragment.from([operatorNode])

      // Replace from startPos to endPos with the fragment
      tr.replaceWith(startPos, endPos, fragment)

      // Position cursor after the operator
      const cursorPos = startPos + fragment.size
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    // Extract all unique characters from the operators list
    const operatorChars = new Set()
    operators.forEach((op) => {
      for (let i = 0; i < op.length; i++) {
        operatorChars.add(op.charAt(i))
      }
    })

    return [
      new Plugin({
        key: new PluginKey('operatorDetection'),
        props: {
          handleTextInput(view, from, to, text) {
            // Only handle operator characters
            if (!operatorChars.has(text)) {
              return false
            }

            // Don't convert if we shouldn't
            if (!shouldConvertOperator(view, from, to, text)) {
              return false
            }

            // Handle the operator
            return handleOperatorTyped(view, from, to, text)
          },
        },
      }),
    ]
  },
})
