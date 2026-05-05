import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from 'prosemirror-state'

const parenMatchHighlightKey = new PluginKey('parenMatchHighlight')

const HIGHLIGHT_CLASS = 'formula-input-field__paren-highlight'
const FUNC_OPENER = '.function-formula-component'
const GROUP_OPENER = '[data-group-opening-paren]'
const FUNC_CLOSER = '[data-formula-closing-paren]'
const GROUP_CLOSER = '[data-group-closing-paren]'
const OPENER_SELECTOR = `${FUNC_OPENER}, ${GROUP_OPENER}`
const CLOSER_SELECTOR = `${FUNC_CLOSER}, ${GROUP_CLOSER}`
const ALL_SELECTOR = `${OPENER_SELECTOR}, ${CLOSER_SELECTOR}`

export function getParenType(el) {
  if (el.matches(FUNC_OPENER) || el.matches(FUNC_CLOSER)) return 'function'
  return 'group'
}

/**
 * Walks all formula-related DOM elements in document order and pairs
 * openers with closers using a stack, handling arbitrary nesting of
 * function calls and grouping parentheses.
 * Only pairs elements of matching types (function↔function, group↔group)
 * so that a missing closer never causes a wrong highlight.
 */
export function collectDOMParenPairs(root) {
  const elements = Array.from(root.querySelectorAll(ALL_SELECTOR))
  const pairs = new Map()
  const stack = []

  for (const el of elements) {
    if (el.matches(OPENER_SELECTOR)) {
      stack.push(el)
    } else if (stack.length > 0) {
      const closerType = getParenType(el)
      if (getParenType(stack[stack.length - 1]) === closerType) {
        const opener = stack.pop()
        pairs.set(opener, el)
        pairs.set(el, opener)
      }
    }
  }

  return pairs
}

export const ParenMatchHighlightExtension = Extension.create({
  name: 'parenMatchHighlight',

  addProseMirrorPlugins() {
    let highlightedEls = []

    const clearHighlights = () => {
      for (const el of highlightedEls) {
        el.classList.remove(HIGHLIGHT_CLASS)
      }
      highlightedEls = []
    }

    return [
      new Plugin({
        key: parenMatchHighlightKey,
        props: {
          handleDOMEvents: {
            mousemove(view, event) {
              const el = event.target?.closest?.(ALL_SELECTOR)

              if (!el || !view.dom.contains(el)) {
                if (highlightedEls.length > 0) clearHighlights()
                return false
              }

              if (highlightedEls.includes(el)) return false

              clearHighlights()

              const pairs = collectDOMParenPairs(view.dom)
              const matched = pairs.get(el)
              if (!matched) return false

              el.classList.add(HIGHLIGHT_CLASS)
              matched.classList.add(HIGHLIGHT_CLASS)
              highlightedEls = [el, matched]

              return false
            },
            mouseleave() {
              clearHighlights()
              return false
            },
          },
        },
      }),
    ]
  },
})
