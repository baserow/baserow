import { Node, mergeAttributes, Extension } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-2'
import GetFormulaComponent from '@baserow/modules/core/components/formula/GetFormulaComponent'
import FunctionFormulaComponent from '@baserow/modules/core/components/formula/FunctionFormulaComponent'

export const GetFormulaComponentNode = Node.create({
  name: 'get-formula-component',
  group: 'inline',
  inline: true,
  draggable: true,

  addAttributes() {
    return {
      path: {
        default: null,
      },
      isSelected: {
        default: false,
      },
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-formula-component="get-formula-component"]',
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, { 'data-formula-component': this.name }),
    ]
  },

  addNodeView() {
    return VueNodeViewRenderer(GetFormulaComponent)
  },
})

export const FunctionFormulaComponentNode = Node.create({
  name: 'function-formula-component',
  group: 'inline',
  inline: true,
  draggable: false,
  selectable: false,

  addAttributes() {
    return {
      functionName: {
        default: null,
      },
      argumentCount: {
        default: 0,
      },
      isSelected: {
        default: false,
      },
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-formula-component="function-formula-component"]',
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, { 'data-formula-component': this.name }),
    ]
  },

  addNodeView() {
    return VueNodeViewRenderer(FunctionFormulaComponent)
  },

  addKeyboardShortcuts() {
    return {
      Backspace: () =>
        this.editor.commands.command(({ state, dispatch }) => {
          const { selection, doc } = state
          const { $from, empty } = selection

          // Only handle when selection is empty (cursor position)
          if (!empty) return false

          // Check if we're immediately after a function-formula-component
          const pos = $from.pos
          let functionNode = null
          let functionPos = null

          // Check position immediately before cursor
          if (pos > 0) {
            const nodeBefore = doc.nodeAt(pos - 1)
            if (
              nodeBefore &&
              nodeBefore.type.name === 'function-formula-component'
            ) {
              functionNode = nodeBefore
              functionPos = pos - 1
            }
          }

          // If not found, check if cursor is at the start of a text node after the function
          if (!functionNode && pos > 1) {
            const nodeBefore = doc.nodeAt(pos - 2)
            if (
              nodeBefore &&
              nodeBefore.type.name === 'function-formula-component'
            ) {
              functionNode = nodeBefore
              functionPos = pos - 2
            }
          }

          if (functionNode && functionPos !== null) {
            // Find the matching closing parenthesis
            let endPos = null
            let parenCount = 1

            // Search from the position after the function node
            const searchStart = functionPos + 1

            doc.nodesBetween(searchStart, doc.content.size, (node, nodePos) => {
              if (parenCount === 0) return false // Stop searching

              if (node.type.name === 'function-closing-paren') {
                parenCount--
                if (parenCount === 0) {
                  endPos = nodePos + node.nodeSize
                  return false
                }
              } else if (node.type.name === 'function-formula-component') {
                // Found a nested function, increment counter
                parenCount++
              }
            })

            // If we found the closing parenthesis, delete everything
            if (endPos !== null && dispatch) {
              dispatch(state.tr.delete(functionPos, endPos))
              return true
            }
          }

          return false
        }),
    }
  },
})

// Atomic comma node for function arguments
export const FunctionArgumentCommaNode = Node.create({
  name: 'function-argument-comma',
  group: 'inline',
  inline: true,
  draggable: false,
  selectable: false,

  parseHTML() {
    return [
      {
        tag: 'span[data-formula-comma="true"]',
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-formula-comma': 'true',
        class: 'formula-field__text-input__comma',
      }),
      ',',
    ]
  },
})

// Node for text segments
export const TextSegmentNode = Node.create({
  name: 'text-segment',
  group: 'inline',
  inline: true,
  content: 'text*',

  parseHTML() {
    return [
      {
        tag: 'span.text-segment',
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        class: 'text-segment',
      }),
      0,
    ]
  },
})

// Atomic closing parenthesis node for functions
export const FunctionClosingParenNode = Node.create({
  name: 'function-closing-paren',
  group: 'inline',
  inline: true,
  draggable: false,
  selectable: false,

  parseHTML() {
    return [
      {
        tag: 'span[data-formula-closing-paren="true"]',
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-formula-closing-paren': 'true',
        class: 'formula-field__text-input__comma', // Reuse same CSS class for consistent style
      }),
      ')',
    ]
  },
})

export const FormulaInsertionExtension = Extension.create({
  name: 'formulaInsertion',

  addCommands() {
    return {
      insertDataComponent:
        (path) =>
        ({ editor, commands }) => {
          commands.insertContent({
            type: 'get-formula-component',
            attrs: { path },
          })

          commands.focus()

          return true
        },
      insertFunction:
        (node) =>
        ({ editor, commands }) => {
          const functionName = node.name

          // Insert the function component node (just name + opening parenthesis)
          commands.insertContent({
            type: 'function-formula-component',
            attrs: {
              functionName,
            },
          })

          // Get minimum args from node signature
          const minArgs = node.signature?.minArgs || 1

          // Add comma-separated placeholders based on minimum args
          if (minArgs >= 2) {
            for (let i = 0; i < minArgs - 1; i++) {
              // Add atomic comma
              commands.insertContent({
                type: 'function-argument-comma',
              })
            }
          }

          // Add closing parenthesis after as atomic node
          commands.insertContent({
            type: 'function-closing-paren',
          })

          // Position cursor at the first argument position
          const { state } = editor
          const { from } = state.selection

          // Calculate cursor position
          // We need to position cursor right after the function component (and opening parenthesis)
          // The function component is 1 node
          let cursorPos = from - 1 // Go back from closing parenthesis

          // If we have placeholders, count them back
          if (minArgs >= 2) {
            // For N arguments, we have (N-1) comma nodes
            cursorPos -= minArgs - 1
          }

          commands.setTextSelection({
            from: cursorPos,
            to: cursorPos,
          })

          commands.focus()

          return true
        },
      insertOperator:
        (node) =>
        ({ editor, commands }) => {
          commands.insertContent(node.signature.operator)

          commands.focus()

          return true
        },
    }
  },
})
