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
    ]

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

            // Special case: if we just skipped a function node, check if it's
            // immediately followed by a closing paren (function with no args)
            if (nextNode.type.name === 'function-formula-component') {
              const $newPos = state.doc.resolve(pos)
              const followingNode = $newPos.nodeAfter

              if (
                followingNode &&
                followingNode.type.name === 'function-closing-paren'
              ) {
                // Skip the closing paren as well
                pos += followingNode.nodeSize
              }
            }

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

          // Skip only ONE skippable node
          if (!skippedNode && skippableNodes.includes(prevNode.type.name)) {
            pos -= prevNode.nodeSize
            moved = true
            skippedNode = true

            // Special case: if we just skipped a closing paren, check if it's
            // immediately preceded by a function node (function with no args)
            if (prevNode.type.name === 'function-closing-paren') {
              const $newPos = state.doc.resolve(pos)
              const precedingNode = $newPos.nodeBefore

              if (
                precedingNode &&
                precedingNode.type.name === 'function-formula-component'
              ) {
                // Skip the function node as well
                pos -= precedingNode.nodeSize
              }
            }

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
