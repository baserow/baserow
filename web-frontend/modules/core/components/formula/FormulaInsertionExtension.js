import { Node, mergeAttributes, Extension } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-2'
import GetFormulaComponent from '@baserow/modules/core/components/formula/GetFormulaComponent'

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
          // Insert zero-width space so cursor can be positioned in the text-segment
          const functionText = functionName + '(\u200B)'

          const { state } = editor
          const startPos = state.selection.from

          commands.insertContent(functionText)

          // Position cursor after the zero-width space (in the text-segment)
          const cursorPos = startPos + functionName.length + 2

          commands.setTextSelection({ from: cursorPos, to: cursorPos })

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
