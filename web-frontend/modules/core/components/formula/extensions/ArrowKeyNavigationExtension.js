import { Extension } from '@tiptap/core'
import { TextSelection } from 'prosemirror-state'

export const ArrowKeyNavigationExtension = Extension.create({
  name: 'arrowKeyNavigation',

  addKeyboardShortcuts() {
    const skippableNodes = [
      'get-formula-component',
      'function-formula-component',
      'operator-formula-component',
      'function-argument-comma',
      'function-closing-paren',
      'group-opening-paren',
      'group-closing-paren',
    ]

    /**
     * Skips closing paren after function with no args when going right
     * @param {object} state - Editor state
     * @param {number} pos - Current position after skipping the function
     * @param {object} functionNode - The function node that was skipped
     * @returns {number} - New position after potentially skipping closing paren
     */
    const skipClosingParenForNoArgFunction = (state, pos, functionNode) => {
      if (functionNode.type.name === 'function-formula-component') {
        const $pos = state.doc.resolve(pos)
        const followingNode = $pos.nodeAfter

        if (
          followingNode &&
          followingNode.type.name === 'function-closing-paren'
        ) {
          return pos + followingNode.nodeSize
        }
      }
      return pos
    }

    /**
     * Skips space and ZWS after minus operator when going right
     * @param {object} state - Editor state
     * @param {number} pos - Current position after skipping the operator
     * @param {object} operatorNode - The operator node that was skipped
     * @returns {number} - New position after skipping space and ZWS
     */
    const skipSpaceAfterMinusOperator = (state, pos, operatorNode) => {
      if (
        operatorNode.type.name === 'operator-formula-component' &&
        operatorNode.attrs.operatorSymbol === '-'
      ) {
        const $pos = state.doc.resolve(pos)
        const followingNode = $pos.nodeAfter

        // Check if the following text starts with a space
        // (it might be in a mixed text node like space+2+ZWS)
        if (
          followingNode &&
          followingNode.isText &&
          followingNode.text?.startsWith(' ')
        ) {
          // Skip just the space character (1 position)
          pos += 1
        }
      }

      return pos
    }

    /**
     * Checks if we should skip a space before a minus operator when going left
     * @param {object} state - Editor state
     * @param {number} pos - Current position
     * @param {object} spaceNode - The space node to check
     * @returns {boolean} - True if space should be skipped
     */
    const shouldSkipSpaceBeforeMinusOperator = (state, pos, spaceNode) => {
      const posBeforeSpace = pos - spaceNode.nodeSize
      const $beforeSpace = state.doc.resolve(posBeforeSpace)
      const nodeBeforeSpace = $beforeSpace.nodeBefore

      return (
        nodeBeforeSpace &&
        nodeBeforeSpace.type.name === 'operator-formula-component' &&
        nodeBeforeSpace.attrs?.operatorSymbol === '-'
      )
    }

    /**
     * Skips function node before closing paren when going left (no args function)
     * @param {object} state - Editor state
     * @param {number} pos - Current position after skipping the closing paren
     * @param {object} closingParenNode - The closing paren node that was skipped
     * @returns {number} - New position after potentially skipping function node
     */
    const skipFunctionBeforeClosingParen = (state, pos, closingParenNode) => {
      if (closingParenNode.type.name === 'function-closing-paren') {
        const $pos = state.doc.resolve(pos)
        const precedingNode = $pos.nodeBefore

        if (
          precedingNode &&
          precedingNode.type.name === 'function-formula-component'
        ) {
          return pos - precedingNode.nodeSize
        }
      }
      return pos
    }

    return {
      ArrowRight: () => {
        const { state, dispatch } = this.editor.view
        const { selection } = state

        if (!selection.empty || selection.from === state.doc.content.size) {
          return false
        }

        const { from } = selection
        let pos = from
        let moved = false
        let skippedNode = false

        // Skip consecutive ZWS, then ONE skippable node, then consecutive ZWS again
        while (pos < state.doc.content.size) {
          const $pos = state.doc.resolve(pos)
          const nextNode = $pos.nodeAfter

          if (!nextNode) break

          // Always skip ZWS
          if (nextNode.isText && nextNode.text === '\u200B') {
            pos += nextNode.nodeSize
            moved = true
            continue
          }

          // Skip only ONE skippable node
          if (!skippedNode && skippableNodes.includes(nextNode.type.name)) {
            pos += nextNode.nodeSize
            moved = true
            skippedNode = true

            // Handle special cases after skipping a node
            pos = skipClosingParenForNoArgFunction(state, pos, nextNode)
            pos = skipSpaceAfterMinusOperator(state, pos, nextNode)

            continue
          }

          // If we already skipped a node, or it's neither ZWS nor skippable, stop
          break
        }

        if (moved) {
          dispatch(state.tr.setSelection(TextSelection.create(state.doc, pos)))
          return true
        }

        return false
      },

      ArrowLeft: () => {
        const { state, dispatch } = this.editor.view
        const { selection } = state

        if (!selection.empty || selection.from === 0) {
          return false
        }

        const { from } = selection
        let pos = from
        let moved = false
        let skippedNode = false

        // Skip consecutive ZWS, then ONE skippable node, then consecutive ZWS again
        while (pos > 0) {
          const $pos = state.doc.resolve(pos)
          const prevNode = $pos.nodeBefore

          if (!prevNode) break

          // Always skip ZWS
          if (prevNode.isText && prevNode.text === '\u200B') {
            pos -= prevNode.nodeSize
            moved = true
            continue
          }

          // Skip space if it's after a minus operator
          if (prevNode.isText && prevNode.text === ' ') {
            if (shouldSkipSpaceBeforeMinusOperator(state, pos, prevNode)) {
              pos -= prevNode.nodeSize
              moved = true
              continue
            }
          }

          // Skip only ONE skippable node
          if (!skippedNode && skippableNodes.includes(prevNode.type.name)) {
            pos -= prevNode.nodeSize
            moved = true
            skippedNode = true

            // Handle special cases after skipping a node
            pos = skipFunctionBeforeClosingParen(state, pos, prevNode)

            continue
          }

          // If we already skipped a node, or it's neither ZWS nor skippable, stop
          break
        }

        if (moved) {
          dispatch(state.tr.setSelection(TextSelection.create(state.doc, pos)))
          return true
        }

        return false
      },
    }
  },
})
