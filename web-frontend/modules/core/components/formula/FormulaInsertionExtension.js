import { Node, mergeAttributes, Extension } from '@tiptap/core'
import { VueNodeViewRenderer } from '@tiptap/vue-2'
import GetFormulaComponent from '@baserow/modules/core/components/formula/GetFormulaComponent'
import FunctionFormulaComponent from '@baserow/modules/core/components/formula/FunctionFormulaComponent'
import OperatorFormulaComponent from '@baserow/modules/core/components/formula/OperatorFormulaComponent'

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
        class: 'formula-input-field__comma',
      }),
      ',',
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
        class: 'formula-input-field__parenthesis',
      }),
      ')',
    ]
  },
})

// Operator formula component node
export const OperatorFormulaComponentNode = Node.create({
  name: 'operator-formula-component',
  group: 'inline',
  inline: true,
  draggable: false,
  selectable: false,

  addAttributes() {
    return {
      operatorSymbol: {
        default: null,
      },
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-formula-component="operator-formula-component"]',
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-formula-component': this.name,
      }),
    ]
  },

  addNodeView() {
    return VueNodeViewRenderer(OperatorFormulaComponent)
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
        ({ editor, commands, state }) => {
          const functionName = node.name
          const minArgs = node.signature?.minArgs || 1

          // Get initial cursor position
          const initialPos = state.selection.from

          // Build all content to insert
          const contentToInsert = []

          // Add function component
          contentToInsert.push({
            type: 'function-formula-component',
            attrs: {
              functionName,
            },
          })

          // Add comma-separated placeholders based on minimum args
          if (minArgs >= 2) {
            for (let i = 0; i < minArgs - 1; i++) {
              contentToInsert.push({
                type: 'function-argument-comma',
              })
            }
          }

          // Add closing parenthesis
          contentToInsert.push({
            type: 'function-closing-paren',
          })

          // Insert all content at once
          commands.insertContent(contentToInsert)

          // Position cursor right after the function component (before commas and closing paren)
          // The function component is 1 node, so cursor should be at initialPos + 1
          const targetPos = initialPos + 1

          commands.setTextSelection({
            from: targetPos,
            to: targetPos,
          })

          commands.focus()

          return true
        },
      insertOperator:
        (node) =>
        ({ editor, commands }) => {
          const operatorSymbol = node.signature.operator

          // Insert operator as an operator-formula-component node
          commands.insertContent({
            type: 'operator-formula-component',
            attrs: {
              operatorSymbol,
            },
          })

          commands.focus()

          return true
        },
    }
  },
})
