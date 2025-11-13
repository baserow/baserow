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

      // Check for compound operators by looking at the previous character
      const textBefore = state.doc.textBetween(Math.max(0, from - 2), from, '')
      let operatorText = typedText
      let startPos = from // Default: insert at current position (don't replace anything before)
      let endPos = from // Default: don't remove anything

      // Handle compound operators (!=, >=, <=)
      if (typedText === '=') {
        // First, check if there's a text character before
        const prevChar = textBefore.charAt(textBefore.length - 1)
        if (prevChar === '!' || prevChar === '>' || prevChar === '<') {
          operatorText = prevChar + '='
          startPos = from - 2 // Start before the !, > or <
          endPos = from // End at current position (don't include the = we're typing)
        } else {
          // Check if there's an operator node right before the cursor
          const $pos = state.doc.resolve(from)
          const nodeBefore = $pos.nodeBefore

          if (
            nodeBefore &&
            nodeBefore.type.name === 'operator-formula-component'
          ) {
            const prevOperator = nodeBefore.attrs.operatorSymbol

            if (
              (prevOperator === '>' || prevOperator === '<') &&
              operators.includes(prevOperator + '=')
            ) {
              // Replace the previous operator node with the compound operator
              operatorText = prevOperator + '='
              startPos = from - nodeBefore.nodeSize
              endPos = from // Replace up to current position
            }
          }
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

            // For '!', we need to wait for the next character to see if it's '!='
            // We don't wait for '>' and '<' because they are valid operators on their own
            if (text === '!') {
              return false
            }

            // Handle the operator
            return handleOperatorTyped(view, to, to, text)
          },
        },
      }),
    ]
  },
})
