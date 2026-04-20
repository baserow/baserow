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

export function buildDetailedParenStack(doc, wrapperStart, pos, functionNames) {
  const stack = []
  const lowerFns = new Set(
    (functionNames || []).map((n) => (n || '').toLowerCase())
  )
  const trailingIdentifier = /[A-Za-z_][A-Za-z0-9_]*$/

  doc.nodesBetween(wrapperStart, pos, (node, nodePos) => {
    if (nodePos >= pos) return false

    if (node.type.name === 'function-formula-component') {
      stack.push({
        kind: 'function',
        node,
        nodeStart: nodePos,
        nodeEnd: nodePos + node.nodeSize,
      })
    } else if (node.type.name === 'group-opening-paren') {
      stack.push({ kind: 'group' })
    } else if (
      node.type.name === 'function-closing-paren' ||
      node.type.name === 'group-closing-paren'
    ) {
      stack.pop()
    } else if (node.isText && node.text) {
      for (let i = 0; i < node.text.length; i++) {
        if (nodePos + i >= pos) break
        const ch = node.text[i]
        if (ch === '(') {
          const match = node.text.slice(0, i).match(trailingIdentifier)
          if (match && lowerFns.has(match[0].toLowerCase())) {
            stack.push({
              kind: 'text-function',
              functionName: match[0],
              functionStart: nodePos + i - match[0].length,
              parenEnd: nodePos + i + 1,
            })
          } else {
            stack.push({ kind: 'group' })
          }
        } else if (ch === ')') {
          stack.pop()
        }
      }
    }
  })

  return stack
}

/**
 * Returns the description of the top-most unclosed opener when it is a
 * text `(` preceded by a known function name. Returns `null` otherwise
 * — including when the top opener is a proper `function-formula-component`
 * / `group-opening-paren` node, or a plain-text `(` that isn't preceded
 * by a function identifier.
 *
 * Typical use: on a typed ')', decide whether to upgrade a pasted
 * `funcName(` text fragment into proper highlighted function nodes
 * instead of closing it as a generic group.
 */
export function findPendingTextFunctionOpen(
  doc,
  wrapperStart,
  pos,
  functionNames
) {
  const stack = buildDetailedParenStack(doc, wrapperStart, pos, functionNames)
  const top = stack.length > 0 ? stack[stack.length - 1] : null
  return top && top.kind === 'text-function' ? top : null
}

/**
 * Returns info about the innermost unclosed `function-formula-component`
 * node when it sits at the top of the opener stack at `pos`. Returns
 * `null` when the top opener is not a proper function node (group,
 * text-function) or when no opener is pending.
 *
 * Typical use: on a typed ')', inherit the function's `hasNoArgs`
 * attribute onto the new `function-closing-paren` so styling stays
 * consistent with the `tryFunctionOpen` flow.
 */
export function findInnermostUnclosedFunctionNode(
  doc,
  wrapperStart,
  pos,
  functionNames
) {
  const stack = buildDetailedParenStack(doc, wrapperStart, pos, functionNames)
  const top = stack.length > 0 ? stack[stack.length - 1] : null
  return top && top.kind === 'function' ? top : null
}
