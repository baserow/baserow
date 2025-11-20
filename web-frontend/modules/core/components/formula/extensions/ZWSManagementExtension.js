import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'

/**
 * Extension that manages Zero-Width Spaces (ZWS) in the formula editor.
 * This extension ensures that:
 * 1. There are no consecutive ZWS (cleanup)
 * 2. Empty argument slots always have at least one ZWS (ensure)
 */
export const ZWSManagementExtension = Extension.create({
  name: 'zwsManagement',

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('zwsManagement'),
        appendTransaction(transactions, oldState, newState) {
          const tr = newState.tr
          let modified = false

          // Phase 1: Clean up consecutive ZWS
          newState.doc.descendants((node, pos) => {
            if (node.isText && node.text) {
              // Check if the text contains multiple consecutive ZWS
              const text = node.text
              if (text.includes('\u200B\u200B')) {
                // Replace multiple consecutive ZWS with a single one
                const cleanedText = text.replace(/\u200B+/g, '\u200B')
                if (cleanedText !== text) {
                  tr.insertText(cleanedText, pos, pos + node.nodeSize)
                  modified = true
                }
              }
            }
          })

          // Apply cleanup changes before checking for missing ZWS
          const docAfterCleanup = modified ? tr.doc : newState.doc

          // Phase 2: Ensure ZWS in empty argument slots
          const argumentStartNodes = [
            'function-formula-component',
            'function-argument-comma',
            'operator-formula-component',
          ]

          const argumentEndNodes = [
            'function-argument-comma',
            'function-closing-paren',
          ]

          const needZWSBeforeNodes = [
            'operator-formula-component',
            'function-argument-comma',
            'function-closing-paren',
          ]

          docAfterCleanup.descendants((node, pos) => {
            // Check for ZWS after argument start nodes
            if (argumentStartNodes.includes(node.type.name)) {
              const afterNodePos = pos + node.nodeSize
              const $afterNode = docAfterCleanup.resolve(afterNodePos)
              const nextNode = $afterNode.nodeAfter

              // Check if the next node is an argument end node (empty argument)
              if (nextNode && argumentEndNodes.includes(nextNode.type.name)) {
                // Empty argument slot! Insert a ZWS
                tr.insert(afterNodePos, newState.schema.text('\u200B'))
                modified = true
              } else if (!nextNode) {
                // End of document after argument start node
                tr.insert(afterNodePos, newState.schema.text('\u200B'))
                modified = true
              }
            }

            // Check for ZWS before nodes that need it
            if (needZWSBeforeNodes.includes(node.type.name)) {
              const $beforeNode = docAfterCleanup.resolve(pos)
              const prevNode = $beforeNode.nodeBefore

              // If the previous node is NOT a ZWS, we need to add one
              if (
                !prevNode ||
                !(prevNode.isText && prevNode.text === '\u200B')
              ) {
                // Check if previous node is an atomic node that marks argument boundary
                if (
                  !prevNode ||
                  prevNode.type.name === 'function-formula-component' ||
                  prevNode.type.name === 'function-argument-comma' ||
                  prevNode.type.name === 'operator-formula-component'
                ) {
                  // Empty left argument! Insert a ZWS
                  tr.insert(pos, newState.schema.text('\u200B'))
                  modified = true
                }
              }
            }
          })

          return modified ? tr : null
        },
      }),
    ]
  },
})
