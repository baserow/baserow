import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import { Mapping } from '@tiptap/pm/transform'
import { isZWSNode } from '@baserow/modules/core/components/formula/extensions/helpers'

/**
 * Walks `doc` with a stack and returns the list of (opener, closer)
 * position pairs for every `function-formula-component` that has a
 * matching `function-closing-paren`, plus the list of already-unmatched
 * opener positions.
 *
 * The stack-based pairing mirrors how the formula parser itself groups
 * parens (LIFO): the innermost opener pairs with the first closer that
 * comes after it. This is the correct pairing for a balanced doc, which
 * is the invariant the extension maintains.
 */
function collectFunctionPairs(doc) {
  const stack = []
  const pairs = []
  const unmatched = []

  doc.descendants((node, pos) => {
    if (node.type.name === 'function-formula-component') {
      stack.push(pos)
    } else if (node.type.name === 'function-closing-paren') {
      const openerPos = stack.pop()
      if (openerPos !== undefined) {
        pairs.push({ openerPos, closerPos: pos })
      }
    }
  })

  while (stack.length > 0) unmatched.push(stack.pop())
  return { pairs, unmatched }
}

/**
 * Combines the per-step maps of every transaction in `transactions`
 * into a single `Mapping` object covering the whole oldState → newState
 * delta. `tr.mapping` already aggregates the steps within one
 * transaction, but appendTransaction receives an array of them and we
 * need a single mapping to trace positions across the whole batch.
 */
function combinedMapping(transactions) {
  const mapping = new Mapping()
  for (const tr of transactions) {
    for (const step of tr.steps) {
      mapping.appendMap(step.getMap())
    }
  }
  return mapping
}

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
 * The opener to downgrade is determined by looking at the (opener, closer)
 * pairs in `oldState` and tracing each position forward through the
 * current transactions. When a pair's closer was deleted but its opener
 * survives, that opener becomes the downgrade target. This correctly
 * handles nested calls like `concat(if(...),"lorem ipsum")`: deleting the inner
 * `)` orphans `if(`, not `concat(` — which a simple newState-only stack
 * walk would misattribute to the outer call.
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

          const { pairs, unmatched } = collectFunctionPairs(oldState.doc)
          if (pairs.length === 0 && unmatched.length === 0) return null

          const mapping = combinedMapping(transactions)

          // Helper: map a position via the combined mapping and return
          // both the new position and whether it was inside a deletion.
          // `assoc` follows PM conventions — for the trailing edge of an
          // atomic node (pos + 1) we bias left so the position is treated
          // as deleted iff the atom itself was removed.
          const mapPos = (pos, assoc) => mapping.mapResult(pos, assoc)

          const orphanOpenersNewPos = []

          for (const { openerPos, closerPos } of pairs) {
            const openerRes = mapPos(openerPos + 1, -1)
            const closerRes = mapPos(closerPos + 1, -1)
            if (!openerRes.deleted && closerRes.deleted) {
              // Opener new position: subtract 1 to go from "just after"
              // back to "just before" the atom.
              orphanOpenersNewPos.push(openerRes.pos - 1)
            }
          }

          // Already-unmatched openers from oldState (defensive — the
          // invariant is that oldState is consistent, but if an older
          // transaction left a dangling opener, propagate it forward).
          for (const openerPos of unmatched) {
            const res = mapPos(openerPos + 1, -1)
            if (!res.deleted) orphanOpenersNewPos.push(res.pos - 1)
          }

          if (orphanOpenersNewPos.length === 0) return null

          // Process in reverse document order so earlier positions stay
          // stable while we build the transaction.
          orphanOpenersNewPos.sort((a, b) => b - a)

          const { schema, doc } = newState
          const tr = newState.tr

          for (const pos of orphanOpenersNewPos) {
            const node = doc.nodeAt(pos)
            if (!node || node.type.name !== 'function-formula-component') {
              continue
            }
            const functionName = node.attrs.functionName || ''
            const text = `${functionName}(`

            // Strip any ZWS immediately adjacent to the atomic node: it
            // existed only as a cursor-positioning marker and becomes
            // redundant once the opener is plain text.
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
