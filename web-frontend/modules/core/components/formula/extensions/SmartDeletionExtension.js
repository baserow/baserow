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
     * Tries to delete a minus operator with its trailing space
     * @returns {object|null} - Deletion range {from, to} or null if not applicable
     */
    const tryDeleteMinusOperatorWithSpace = (state, from, isBackward) => {
      const $pos = state.doc.resolve(from)
      const adjacentNode = isBackward ? $pos.nodeBefore : $pos.nodeAfter

      // Check if we're adjacent to a space
      if (adjacentNode && adjacentNode.isText && adjacentNode.text === ' ') {
        const posOtherSideSpace = isBackward
          ? from - adjacentNode.nodeSize
          : from + adjacentNode.nodeSize
        const $otherSideSpace = state.doc.resolve(posOtherSideSpace)
        const nodeOtherSideSpace = isBackward
          ? $otherSideSpace.nodeBefore
          : $otherSideSpace.nodeAfter

        // Check if the other side is a minus operator
        if (
          nodeOtherSideSpace &&
          nodeOtherSideSpace.type.name === 'operator-formula-component' &&
          nodeOtherSideSpace.attrs.operatorSymbol === '-'
        ) {
          if (isBackward) {
            // Backspace: delete operator + space, and ZWS after if present
            const $afterSpace = state.doc.resolve(from)
            const nodeAfterSpace = $afterSpace.nodeAfter

            const deleteFrom = posOtherSideSpace - nodeOtherSideSpace.nodeSize
            const deleteTo =
              nodeAfterSpace &&
              nodeAfterSpace.isText &&
              nodeAfterSpace.text === '\u200B'
                ? from + nodeAfterSpace.nodeSize
                : from

            return { from: deleteFrom, to: deleteTo }
          }
        }
      }

      return null
    }

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

      // Try to delete minus operator with space (special case)
      const minusDeletion = tryDeleteMinusOperatorWithSpace(
        state,
        from,
        isBackward
      )
      if (minusDeletion) {
        const tr = state.tr
        tr.delete(minusDeletion.from, minusDeletion.to)
        dispatch(tr)
        return true
      }

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
