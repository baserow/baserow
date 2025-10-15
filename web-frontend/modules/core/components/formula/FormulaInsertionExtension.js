import { Node, mergeAttributes, Extension } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-2'
import GetFormulaComponent from '@baserow/modules/core/components/formula/GetFormulaComponent'

export const GetFormulaComponentNode = Node.create({
  name: 'get',
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
        tag: 'span[data-formula-component="get"]',
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
            type: 'get',
            attrs: { path },
          })

          commands.focus()

          return true
        },
      insertFunction:
        (node) =>
        ({ editor, commands }) => {
          const functionName = node.name
          const functionText = functionName + '()'

          const { state } = editor
          const startPos = state.selection.from

          commands.insertContent(functionText)

          const cursorPos = startPos + functionName.length + 1

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
