import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Decoration, DecorationSet } from '@tiptap/pm/view'

export const FunctionArgumentHighlightExtension = Extension.create({
  name: 'functionArgumentHighlight',

  addProseMirrorPlugins() {
    const getDecorations = (doc) => {
      const decorations = []

      doc.descendants((node, pos) => {
        // Check if this is a function-formula-component node
        if (node.type.name === 'function-formula-component') {
          // Process content to find commas
          let offset = pos + 1 // Start after the node opening

          node.content.forEach((child, childOffset, index) => {
            if (child.isText && child.text.includes(',')) {
              // Find all comma positions
              for (let i = 0; i < child.text.length; i++) {
                if (child.text[i] === ',') {
                  decorations.push(
                    Decoration.inline(
                      offset + childOffset + i,
                      offset + childOffset + i + 1,
                      {
                        class: 'function-argument-comma',
                      }
                    )
                  )
                }
              }
            }
            offset += child.nodeSize
          })
        }
      })

      return DecorationSet.create(doc, decorations)
    }

    return [
      new Plugin({
        key: new PluginKey('functionArgumentHighlight'),

        state: {
          init(_, { doc }) {
            return getDecorations(doc)
          },
          apply(transaction, oldState) {
            return transaction.docChanged
              ? getDecorations(transaction.doc)
              : oldState
          },
        },

        props: {
          decorations(state) {
            return this.getState(state)
          },
        },
      }),
    ]
  },
})
