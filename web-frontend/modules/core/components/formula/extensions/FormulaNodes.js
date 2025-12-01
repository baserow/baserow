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
  atom: true,
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
      hasNoArgs: {
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

  renderHTML({ node, HTMLAttributes }) {
    const attrs = { 'data-formula-component': this.name }
    if (node.attrs.hasNoArgs) {
      attrs['data-no-args'] = 'true'
    }
    return ['span', mergeAttributes(HTMLAttributes, attrs)]
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
  atom: true,
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
  atom: true,
  draggable: false,
  selectable: false,

  addAttributes() {
    return {
      noArgs: {
        default: false,
      },
    }
  },

  parseHTML() {
    return [
      {
        tag: 'span[data-formula-closing-paren="true"]',
      },
    ]
  },

  renderHTML({ node, HTMLAttributes }) {
    const attrs = {
      'data-formula-closing-paren': 'true',
      class: 'formula-input-field__parenthesis',
    }
    if (node.attrs.noArgs) {
      attrs['data-no-args'] = 'true'
    }
    return ['span', mergeAttributes(HTMLAttributes, attrs), ')']
  },
})

// Atomic opening parenthesis node for grouping
export const GroupOpeningParenNode = Node.create({
  name: 'group-opening-paren',
  group: 'inline',
  inline: true,
  atom: true,
  draggable: false,
  selectable: false,

  parseHTML() {
    return [
      {
        tag: 'span[data-group-opening-paren="true"]',
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-group-opening-paren': 'true',
        class: 'formula-input-field__group-parenthesis',
      }),
      '(',
    ]
  },
})

// Atomic closing parenthesis node for grouping
export const GroupClosingParenNode = Node.create({
  name: 'group-closing-paren',
  group: 'inline',
  inline: true,
  atom: true,
  draggable: false,
  selectable: false,

  parseHTML() {
    return [
      {
        tag: 'span[data-group-closing-paren="true"]',
      },
    ]
  },

  renderHTML({ HTMLAttributes }) {
    return [
      'span',
      mergeAttributes(HTMLAttributes, {
        'data-group-closing-paren': 'true',
        class: 'formula-input-field__group-parenthesis',
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
  atom: true,
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
          commands.insertContent([
            {
              type: 'text',
              text: '\u200B',
            },
            {
              type: 'get-formula-component',
              attrs: { path },
            },
            {
              type: 'text',
              text: '\u200B',
            },
          ])

          commands.focus()

          return true
        },
      insertFunction:
        (node) =>
        ({ editor, commands, state }) => {
          const functionName = node.name
          const minArgs = node.signature?.minArgs || 0

          // Get initial cursor position
          const initialPos = state.selection.from

          // Build all content to insert
          const contentToInsert = []

          // Add ZWS before the function component
          contentToInsert.push({ type: 'text', text: '\u200B' })

          // Add function component
          contentToInsert.push({
            type: 'function-formula-component',
            attrs: {
              functionName,
              hasNoArgs: minArgs === 0,
            },
          })

          // Add argument placeholders if needed
          if (minArgs > 0) {
            contentToInsert.push({ type: 'text', text: '\u200B' }) // First argument
            for (let i = 1; i < minArgs; i++) {
              contentToInsert.push({ type: 'function-argument-comma' })
              contentToInsert.push({ type: 'text', text: '\u200B' }) // Subsequent arguments
            }
          }

          // Add closing parenthesis
          contentToInsert.push({
            type: 'function-closing-paren',
            attrs: {
              noArgs: minArgs === 0,
            },
          })

          // Always add a ZWS after the whole function call
          // CleanupZWSExtension will remove any consecutive ZWS automatically
          contentToInsert.push({ type: 'text', text: '\u200B' })

          // Insert all content at once
          commands.insertContent(contentToInsert)

          // Position cursor:
          // - If no arguments expected, place after closing paren (but before the final ZWS)
          // - Otherwise, place right after the function component (in first argument slot)
          let targetPos
          if (minArgs === 0) {
            // ZWS (1) + functionNode (1) + closingParenNode (1) = 3
            // We place cursor at position 3, which is after the closing paren but before the final ZWS
            targetPos = initialPos + 3
          } else {
            // ZWS (1) + functionNode (1) = 2 (in first argument slot)
            targetPos = initialPos + 2
          }

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

          // Build content to insert
          const contentToInsert = [
            { type: 'text', text: '\u200B' },
            {
              type: 'operator-formula-component',
              attrs: {
                operatorSymbol,
              },
            },
          ]

          // Add space after minus operator to distinguish from negative numbers
          if (operatorSymbol === '-') {
            contentToInsert.push({ type: 'text', text: ' ' })
          }

          contentToInsert.push({ type: 'text', text: '\u200B' })

          commands.insertContent(contentToInsert)

          commands.focus()

          return true
        },
    }
  },
})
