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
