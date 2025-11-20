import { Extension } from '@tiptap/core'
import { TextSelection } from '@tiptap/pm/state'

export const SmartBackspaceExtension = Extension.create({
  name: 'smartBackspace',

  addKeyboardShortcuts() {
    const atomicNodes = [
      'get-formula-component',
      'function-formula-component',
      'operator-formula-component',
      'function-argument-comma',
      'function-closing-paren',
    ]

    return {
      Backspace: () => {
        const { state, dispatch } = this.editor.view
        const { selection } = state

        // Only handle when selection is empty (cursor, not selection)
        if (!selection.empty || selection.from === 0) {
          return false
        }

        const { from } = selection
        const $pos = state.doc.resolve(from)
        const nodeBefore = $pos.nodeBefore

        // Check if the node before cursor is a ZWS
        if (nodeBefore && nodeBefore.isText && nodeBefore.text === '\u200B') {
          // Get the position before the ZWS
          const posBeforeZWS = from - nodeBefore.nodeSize
          const $posBeforeZWS = state.doc.resolve(posBeforeZWS)
          const nodeBeforeZWS = $posBeforeZWS.nodeBefore

          // Check if the node before ZWS is an atomic node
          if (nodeBeforeZWS && atomicNodes.includes(nodeBeforeZWS.type.name)) {
            // Delete both the ZWS and the atomic node
            const tr = state.tr
            const deleteFrom = posBeforeZWS - nodeBeforeZWS.nodeSize
            const deleteTo = from

            tr.delete(deleteFrom, deleteTo)
            dispatch(tr)
            return true
          }
        }

        return false
      },
    }
  },
})
