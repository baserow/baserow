// ── ZWS constants and helpers ──────────────────────────────────────

export const ZWS = '\u200B'
export const ZWS_REGEX = /\u200B/g
export const CONSECUTIVE_ZWS_REGEX = /\u200B+/g

export function isZWSNode(node) {
  return node?.isText && node.text && /^\u200B+$/.test(node.text)
}

export function zwsTextJSON() {
  return { type: 'text', text: ZWS }
}

export function zwsTextNode(schema) {
  return schema.text(ZWS)
}

// ── ProseMirror document helpers ───────────────────────────────────

/**
 * Returns the text content from the text node at the cursor position,
 * up to the cursor offset. Uses $pos for direct node access instead
 * of doc.textBetween, which skips atom nodes and produces a concatenated
 * string whose character positions don't correspond to document positions.
 */
export function getTextBeforeCursor(doc, from) {
  const $pos = doc.resolve(from)

  if ($pos.textOffset > 0) {
    const textNode = $pos.parent.child($pos.index())
    return textNode.text.slice(0, $pos.textOffset)
  }

  if ($pos.nodeBefore && $pos.nodeBefore.isText) {
    return $pos.nodeBefore.text
  }

  return ''
}

/**
 * Scans forward from `from`, skipping over ZWS-only text nodes,
 * and returns the first non-ZWS node found (with its position).
 * Used for overtype behaviour: when the cursor is followed only by
 * ZWS and then a closing paren, we move past it instead of inserting
 * a duplicate.
 */
export function findNextNonZWSNode(doc, from) {
  let pos = from
  const $pos = doc.resolve(pos)

  if ($pos.textOffset > 0) {
    const textNode = $pos.parent.child($pos.index())
    const remaining = textNode.text.slice($pos.textOffset)
    if (!/^\u200B*$/.test(remaining)) return null
    pos += remaining.length
  }

  let $current = doc.resolve(pos)
  while ($current.nodeAfter) {
    const next = $current.nodeAfter
    if (next.isText && /^\u200B+$/.test(next.text)) {
      pos += next.nodeSize
      $current = doc.resolve(pos)
      continue
    }
    return { node: next, pos }
  }

  return null
}

/**
 * Builds a stack representing currently-open parentheses between
 * wrapperStart and pos. Each entry is 'function' or 'group'.
 * The top of the stack tells what the next ')' would close.
 */
export function buildParenStack(doc, wrapperStart, pos) {
  const stack = []

  doc.nodesBetween(wrapperStart, pos, (node, nodePos) => {
    if (nodePos >= pos) return false

    if (node.type.name === 'function-formula-component') {
      stack.push('function')
    } else if (node.type.name === 'group-opening-paren') {
      stack.push('group')
    } else if (
      node.type.name === 'function-closing-paren' ||
      node.type.name === 'group-closing-paren'
    ) {
      stack.pop()
    } else if (node.isText && node.text) {
      for (let i = 0; i < node.text.length; i++) {
        if (nodePos + i >= pos) break
        if (node.text[i] === '(') {
          stack.push('group')
        } else if (node.text[i] === ')') {
          stack.pop()
        }
      }
    }
  })

  return stack
}
