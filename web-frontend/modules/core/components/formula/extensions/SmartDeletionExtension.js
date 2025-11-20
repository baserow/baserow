import { Extension } from '@tiptap/core'

/**
 * Extension that provides smart deletion behavior for atomic nodes.
 * When deleting (Backspace or Delete) near an atomic node with adjacent ZWS,
 * both the node and the ZWS are deleted together in a single keystroke.
 */
export const SmartDeletionExtension = Extension.create({
  name: 'smartDeletion',

  addKeyboardShortcuts() {
    const atomicNodes = [
      'get-formula-component',
      'function-formula-component',
      'operator-formula-component',
      'function-argument-comma',
      'function-closing-paren',
      'group-opening-paren',
      'group-closing-paren',
    ]

    /**
     * Handles smart deletion in a given direction
     * @param {boolean} isBackward - true for Backspace, false for Delete
     */
    const handleSmartDeletion = (isBackward) => {
      const { state, dispatch } = this.editor.view
      const { selection } = state

      // Check boundaries
      if (!selection.empty) {
        return false
      }
      if (isBackward && selection.from === 0) {
        return false
      }
      if (!isBackward && selection.from === state.doc.content.size) {
        return false
      }

      const { from } = selection
      const $pos = state.doc.resolve(from)
      const adjacentNode = isBackward ? $pos.nodeBefore : $pos.nodeAfter

      // Check if the adjacent node is a ZWS
      if (
        adjacentNode &&
        adjacentNode.isText &&
        adjacentNode.text === '\u200B'
      ) {
        // Get the position on the other side of the ZWS
        const posOtherSideZWS = isBackward
          ? from - adjacentNode.nodeSize
          : from + adjacentNode.nodeSize
        const $posOtherSide = state.doc.resolve(posOtherSideZWS)
        const nodeOtherSide = isBackward
          ? $posOtherSide.nodeBefore
          : $posOtherSide.nodeAfter

        // Check if the node on the other side is an atomic node
        if (nodeOtherSide && atomicNodes.includes(nodeOtherSide.type.name)) {
          // Delete both the ZWS and the atomic node
          const tr = state.tr
          const deleteFrom = isBackward
            ? posOtherSideZWS - nodeOtherSide.nodeSize
            : from
          const deleteTo = isBackward
            ? from
            : posOtherSideZWS + nodeOtherSide.nodeSize

          tr.delete(deleteFrom, deleteTo)
          dispatch(tr)
          return true
        }
      }

      return false
    }

    return {
      Backspace: () => handleSmartDeletion(true),
      Delete: () => handleSmartDeletion(false),
    }
  },
})
