import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import {
  ZWS,
  CONSECUTIVE_ZWS_REGEX,
  isZWSNode,
  zwsTextNode,
} from '@baserow/modules/core/components/formula/extensions/helpers'

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
          if (!transactions.some((t) => t.docChanged)) return null

          const tr = newState.tr

          // Phase 1: Clean up consecutive ZWS.
          // Collect replacements first, then apply in reverse order to avoid
          // position drift.
          const zwsReplacements = []
          newState.doc.descendants((node, pos) => {
            if (node.isText && node.text) {
              const text = node.text
              if (text.includes(ZWS + ZWS)) {
                const cleanedText = text.replace(CONSECUTIVE_ZWS_REGEX, ZWS)
                if (cleanedText !== text) {
                  zwsReplacements.push({
                    cleanedText,
                    pos,
                    end: pos + node.nodeSize,
                  })
                }
              }
            }
          })
          let modified = Boolean(zwsReplacements.length)
          for (const { cleanedText, pos, end } of zwsReplacements.reverse()) {
            tr.insertText(cleanedText, pos, end)
          }

          // Apply cleanup changes before checking for missing ZWS
          const docAfterCleanup = modified ? tr.doc : newState.doc

          // Phase 2: Ensure ZWS in empty argument slots.
          // Collect insertions and apply in reverse to avoid position drift.
          const argumentStartNodes = [
            'function-formula-component',
            'function-argument-comma',
            'operator-formula-component',
            'group-opening-paren',
          ]

          const argumentEndNodes = [
            'function-argument-comma',
            'function-closing-paren',
            'group-closing-paren',
          ]

          const needZWSBeforeNodes = [
            'operator-formula-component',
            'function-argument-comma',
            'function-closing-paren',
            'group-closing-paren',
          ]

          const insertions = []

          docAfterCleanup.descendants((node, pos) => {
            if (argumentStartNodes.includes(node.type.name)) {
              const afterNodePos = pos + node.nodeSize
              const $afterNode = docAfterCleanup.resolve(afterNodePos)
              const nextNode = $afterNode.nodeAfter

              if (nextNode && argumentEndNodes.includes(nextNode.type.name)) {
                insertions.push(afterNodePos)
              } else if (!nextNode) {
                insertions.push(afterNodePos)
              }
            }

            if (needZWSBeforeNodes.includes(node.type.name)) {
              const $beforeNode = docAfterCleanup.resolve(pos)
              const prevNode = $beforeNode.nodeBefore

              if (!prevNode || !isZWSNode(prevNode)) {
                if (
                  !prevNode ||
                  prevNode.type.name === 'function-formula-component' ||
                  prevNode.type.name === 'function-argument-comma' ||
                  prevNode.type.name === 'operator-formula-component' ||
                  prevNode.type.name === 'group-opening-paren'
                ) {
                  insertions.push(pos)
                }
              }
            }
          })

          if (insertions.length > 0) {
            modified = true
            const uniquePositions = [...new Set(insertions)].sort(
              (a, b) => b - a
            )
            for (const insertPos of uniquePositions) {
              tr.insert(insertPos, zwsTextNode(newState.schema))
            }
          }

          return modified ? tr : null
        },
      }),
    ]
  },
})
