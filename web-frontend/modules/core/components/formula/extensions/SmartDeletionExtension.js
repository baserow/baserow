import { Extension } from '@tiptap/core'
import { isZWSNode } from '@baserow/modules/core/components/formula/extensions/helpers'

/**
 * Scans forward from `afterFunctionPos` to find the function-closing-paren
 * and all function-argument-comma nodes that directly belong to the deleted
 * function-formula-component. Also includes the ZWS nodes immediately
 * surrounding those structural nodes so that no stray invisible characters
 * remain in the document after deletion.
 *
 * A Map keyed by position is used to deduplicate entries (e.g. a single ZWS
 * that sits between two commas would otherwise be collected twice).
 *
 * Nested function calls are tracked so that their own commas and closing
 * parens are not mistaken for direct children of the deleted function.
 */
function findMatchedFunctionStructure(doc, afterFunctionPos) {
  const byPos = new Map()

  const add = (pos, size) => {
    if (!byPos.has(pos)) byPos.set(pos, { pos, size })
  }

  const addWithAdjacentZWS = (pos, size) => {
    // ZWS immediately before this node
    const $before = doc.resolve(pos)
    const prevNode = $before.nodeBefore
    if (prevNode && isZWSNode(prevNode)) {
      add(pos - prevNode.nodeSize, prevNode.nodeSize)
    }

    add(pos, size)

    // ZWS immediately after this node
    const $after = doc.resolve(pos + size)
    const nextNode = $after.nodeAfter
    if (nextNode && isZWSNode(nextNode)) {
      add(pos + size, nextNode.nodeSize)
    }
  }

  let nestedDepth = 0
  let closerFound = false

  doc.nodesBetween(afterFunctionPos, doc.content.size, (node, pos) => {
    if (closerFound) return
    const name = node.type.name
    if (name === 'function-formula-component') {
      nestedDepth++
    } else if (name === 'function-closing-paren') {
      if (nestedDepth === 0) {
        addWithAdjacentZWS(pos, node.nodeSize)
        closerFound = true
        return false
      }
      nestedDepth--
    } else if (name === 'function-argument-comma' && nestedDepth === 0) {
      addWithAdjacentZWS(pos, node.nodeSize)
    }
  })

  return [...byPos.values()]
}

/**
 * Extension that provides smart deletion behavior for atomic nodes.
 * When deleting (Backspace or Delete) near an atomic node with adjacent ZWS,
 * both the node and the ZWS are deleted together in a single keystroke.
 *
 * For function-formula-component nodes, the deletion also cascades to the
 * matched function-closing-paren and all direct function-argument-comma
 * nodes, keeping only the argument content.
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
            const deleteTo = isZWSNode(nodeAfterSpace)
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

      // Case A: Adjacent node is a ZWS — check what's on the other side of it.
      if (adjacentNode && isZWSNode(adjacentNode)) {
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
          const deleteFrom = isBackward
            ? posOtherSideZWS - nodeOtherSide.nodeSize
            : from
          const deleteTo = isBackward
            ? from
            : posOtherSideZWS + nodeOtherSide.nodeSize

          const tr = state.tr

          if (nodeOtherSide.type.name === 'function-formula-component') {
            // Cascade: scan from posOtherSideZWS (= end of function node) to
            // find its matched closing paren and direct arg commas.
            const extra = findMatchedFunctionStructure(
              state.doc,
              posOtherSideZWS
            )
            const allDeletions = [
              { pos: deleteFrom, size: deleteTo - deleteFrom },
              ...extra,
            ].sort((a, b) => b.pos - a.pos)
            for (const { pos, size } of allDeletions) {
              tr.delete(pos, pos + size)
            }
          } else {
            tr.delete(deleteFrom, deleteTo)
          }

          dispatch(tr)
          return true
        }
      }

      // Case B: Cursor is directly adjacent to a function-formula-component
      // (no ZWS between them). This happens when loaded formulas have no ZWS
      // after the function opener, or after the first argument slot's ZWS was
      // consumed by typed content and then deleted.
      if (
        adjacentNode &&
        !adjacentNode.isText &&
        adjacentNode.type.name === 'function-formula-component'
      ) {
        const deleteFrom = isBackward ? from - adjacentNode.nodeSize : from
        const deleteTo = isBackward ? from : from + adjacentNode.nodeSize
        const tr = state.tr

        const extra = findMatchedFunctionStructure(state.doc, deleteTo)

        // In Case B we don't delete a trailing ZWS as part of the main range,
        // so if there is a ZWS immediately after the function node include it.
        const $afterFn = state.doc.resolve(deleteTo)
        const nodeAfterFn = $afterFn.nodeAfter
        const mainSize =
          nodeAfterFn && isZWSNode(nodeAfterFn)
            ? deleteTo - deleteFrom + nodeAfterFn.nodeSize
            : deleteTo - deleteFrom

        const allDeletions = [
          { pos: deleteFrom, size: mainSize },
          ...extra,
        ].sort((a, b) => b.pos - a.pos)
        for (const { pos, size } of allDeletions) {
          tr.delete(pos, pos + size)
        }

        dispatch(tr)
        return true
      }

      return false
    }

    return {
      Backspace: () => handleSmartDeletion(true),
      Delete: () => handleSmartDeletion(false),
    }
  },
})
