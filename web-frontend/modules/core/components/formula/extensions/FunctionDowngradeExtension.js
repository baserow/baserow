import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { isZWSNode } from '@baserow/modules/core/components/formula/extensions/helpers'

/**
 * Keeps the document consistent after a deletion: when a
 * `function-closing-paren` has been removed (typically by Backspace right
 * after it) and its matching `function-formula-component` no longer has a
 * closer, the function opener is downgraded to plain text `funcName(`.
 *
 * This mirrors the rendering of a pasted unclosed `funcName(` — which the
 * tolerant parser (`_renderPartialCall`) also leaves as plain text — so
 * the visual state of a partial call stays consistent across both flows
 * (highlighted only when balanced, plain text otherwise).
 *
 * Typing ')' afterwards will still re-upgrade the text `funcName(` back
 * to a proper highlighted function node via `upgradeTextFunctionOnClose`.
 */
export const FunctionDowngradeExtension = Extension.create({
  name: 'functionDowngrade',

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey('functionDowngrade'),

        appendTransaction(transactions, oldState, newState) {
          if (!transactions.some((tr) => tr.docChanged)) return null

          // Walk the doc with a stack: every `function-formula-component`
          // pushes, every `function-closing-paren` pops. What remains in
          // the stack at the end is the list of unmatched openers.
          const stack = []
          newState.doc.descendants((node, pos) => {
            if (node.type.name === 'function-formula-component') {
              stack.push({ node, pos })
            } else if (node.type.name === 'function-closing-paren') {
              stack.pop()
            }
          })

          if (stack.length === 0) return null

          // Downgrade each unmatched function to plain text `funcName(`.
          // Process in reverse document order so replacements at higher
          // positions don't shift the positions of earlier ones.
          stack.sort((a, b) => b.pos - a.pos)
          const { schema, doc } = newState
          const tr = newState.tr

          for (const { node, pos } of stack) {
            const functionName = node.attrs.functionName || ''
            const text = `${functionName}(`

            // Strip any ZWS immediately adjacent to the atomic node: it
            // existed only as a cursor-positioning marker around that
            // atom and becomes redundant once the opener is plain text.
            let from = pos
            let to = pos + node.nodeSize
            const $before = doc.resolve(from)
            if (isZWSNode($before.nodeBefore)) {
              from -= $before.nodeBefore.nodeSize
            }
            const $after = doc.resolve(to)
            if (isZWSNode($after.nodeAfter)) {
              to += $after.nodeAfter.nodeSize
            }

            tr.replaceWith(from, to, schema.text(text))
          }

          return tr
        },
      }),
    ]
  },
})
