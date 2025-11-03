import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from 'prosemirror-state'

const functionAutoCompletePluginKey = new PluginKey('functionAutoComplete')

/**
 * @name FunctionAutoCompleteExtension
 * @description This Tiptap extension enhances the user experience by automatically
 * closing parentheses for function calls. When a user types a recognized function
 * name followed by an opening parenthesis `(`, this extension inserts the matching
 * closing parenthesis `)` and places the cursor in between them, ready for argument
 * input.
 */
export const FunctionAutoCompleteExtension = Extension.create({
  name: 'functionAutoComplete',

  addOptions() {
    return {
      functionNames: [],
    }
  },

  addProseMirrorPlugins() {
    const functionNames = this.options.functionNames

    // Helper function to check if cursor is inside a string literal
    // (closed or after an unclosed quote)
    const isInsideString = (text) => {
      const ranges = []
      let i = 0

      // Find all closed string ranges
      while (i < text.length) {
        const ch = text[i]

        if (ch === '"' || ch === "'") {
          const quoteChar = ch
          const startIdx = i
          let escaped = false
          i++

          // Find the closing quote
          while (i < text.length) {
            const currentChar = text[i]

            if (escaped) {
              escaped = false
              i++
              continue
            }

            if (currentChar === '\\') {
              escaped = true
              i++
              continue
            }

            if (currentChar === quoteChar) {
              // Found closing quote
              ranges.push({ start: startIdx, end: i })
              i++
              break
            }

            i++
          }
        } else {
          i++
        }
      }

      // Check if the last position is inside any closed string range
      const lastPos = text.length - 1
      if (
        ranges.some((range) => lastPos > range.start && lastPos < range.end)
      ) {
        return true
      }

      // Also check if we're after an unclosed quote
      let inSingleQuote = false
      let inDoubleQuote = false
      let escaped = false

      for (let idx = 0; idx < text.length; idx++) {
        const ch = text[idx]

        if (escaped) {
          escaped = false
          continue
        }

        if (ch === '\\') {
          escaped = true
          continue
        }

        if (ch === "'" && !inDoubleQuote) {
          inSingleQuote = !inSingleQuote
        } else if (ch === '"' && !inSingleQuote) {
          inDoubleQuote = !inDoubleQuote
        }
      }

      return inSingleQuote || inDoubleQuote
    }

    return [
      new Plugin({
        key: functionAutoCompletePluginKey,
        props: {
          handleTextInput(view, from, to, text) {
            const { state } = view
            const { doc } = state

            if (text === '(') {
              const textBefore =
                doc.textBetween(Math.max(0, from - 20), to) + text

              // Check if we're inside a string literal
              if (isInsideString(textBefore)) {
                return false
              }

              if (functionNames.length === 0) {
                return false
              }

              const functionPattern = new RegExp(
                `\\b(${functionNames.join('|')})\\s*\\($`,
                'i'
              )
              const match = textBefore.match(functionPattern)

              if (match) {
                const tr = state.tr

                tr.insertText(text, from, to)

                tr.insertText(')', from + 1)

                tr.setSelection(
                  state.selection.constructor.near(tr.doc.resolve(from + 1))
                )

                view.dispatch(tr)
                return true
              }
            }

            return false
          },
        },
      }),
    ]
  },
})
