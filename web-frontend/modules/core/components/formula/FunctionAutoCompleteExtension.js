import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from 'prosemirror-state'
import { isInsideStringInText } from './FormulaExtensionHelpers'

const functionAutoCompletePluginKey = new PluginKey('functionAutoComplete')

/**
 * @name FunctionAutoCompleteExtension
 * @description This Tiptap extension enhances the user experience by automatically
 * closing parentheses for function calls. When a user types a recognized function
 * name followed by an opening parenthesis `(`, this extension inserts the matching
 * closing parenthesis `)` and places the cursor in between them, ready for argument
 * input. It also adds spacing after commas to position the cursor in a text-segment.
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
              if (isInsideStringInText(textBefore)) {
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

                // Insert zero-width space and closing parenthesis
                tr.insertText('\u200B)', from + 1)

                // Position cursor after the zero-width space (in the text-segment)
                tr.setSelection(
                  state.selection.constructor.near(tr.doc.resolve(from + 2))
                )

                view.dispatch(tr)
                return true
              }
            }

            // Handle comma input to add space and position cursor in text-segment
            if (text === ',') {
              // Check if we're inside a string literal
              const textBefore = doc.textBetween(Math.max(0, from - 20), to)
              if (isInsideStringInText(textBefore + text)) {
                return false
              }

              const tr = state.tr

              // Insert comma followed by zero-width space
              tr.insertText(',\u200B', from, to)

              // Position cursor after the zero-width space (in the text-segment)
              tr.setSelection(
                state.selection.constructor.near(tr.doc.resolve(from + 2))
              )

              view.dispatch(tr)
              return true
            }

            return false
          },
        },
      }),
    ]
  },
})
