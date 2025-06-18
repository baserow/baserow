import { Extension } from '@tiptap/core'
import { RuntimeGet } from '@baserow/modules/core/runtimeFormulaTypes'

/**
 * @name FormulaInsertionExtension
 * @description A Tiptap extension that provides a suite of commands for intelligently
 * inserting various types of content into the formula editor. This includes functions,
 * operators, data components, and plain text, often with smart cursor placement and
 * contextual spacing.
 */
export const FormulaInsertionExtension = Extension.create({
  name: 'formulaInsertion',

  addOptions() {
    return {
      vueComponent: null,
    }
  },

  addCommands() {
    return {
      insertFunction:
        (functionInfo) =>
        ({ editor, commands }) => {
          const functionName = functionInfo.name
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
        (operatorInfo) =>
        ({ commands }) => {
          commands.insertContent(operatorInfo.operator || operatorInfo.name)

          commands.focus()

          return true
        },

      insertDataComponent:
        (path) =>
        ({ editor, commands }) => {
          const { vueComponent } = this.options

          if (!vueComponent) {
            console.warn('FormulaInsertionExtension: vueComponent not provided')
            return false
          }

          const selectedNode = commands.getSelectedNode()
          const isInEditingMode = selectedNode !== null

          if (isInEditingMode) {
            selectedNode.attrs.path = path

            if (vueComponent.emitChange) {
              vueComponent.emitChange()
            }
          } else {
            try {
              const getNode = new RuntimeGet().toNode([{ text: path }])
              commands.insertContent(getNode)
            } catch (error) {
              console.error('Error creating DataExplorer component:', error)
              return false
            }
          }

          commands.focus()

          return true
        },
    }
  },

  addKeyboardShortcuts() {
    return {
      'Mod-Space': () => {
        return false
      },
    }
  },
})
