import { Extension } from '@tiptap/core'
import { Plugin, PluginKey, TextSelection } from '@tiptap/pm/state'
import { Fragment } from '@tiptap/pm/model'
import {
  buildParenStack,
  getTextBeforeCursor,
  findNextNonZWSNode,
} from '@baserow/modules/core/components/formula/extensions/helpers'

export const GroupDetectionExtension = Extension.create({
  name: 'groupDetection',

  addOptions() {
    return {
      functionNames: [],
    }
  },

  addProseMirrorPlugins() {
    const functionNames = this.options.functionNames

    function handleOpeningParenthesis(view, from, to) {
      const { state } = view
      const { doc } = state

      const textBefore = getTextBeforeCursor(doc, from)

      if (functionNames.length > 0 && textBefore) {
        const functionPattern = new RegExp(
          `(^|[^a-zA-Z0-9_])(${functionNames.join('|')})(\\s*)$`,
          'i'
        )

        if (functionPattern.test(textBefore)) {
          return false
        }
      }

      // This is a grouping parenthesis
      const tr = state.tr

      // Create the group opening paren node with a ZWS after
      const nodesToInsert = [
        state.schema.text('\u200B'),
        state.schema.nodes['group-opening-paren'].create(),
        state.schema.text('\u200B'),
      ]

      const fragment = Fragment.from(nodesToInsert)
      tr.replaceWith(from, to, fragment)

      // Position cursor after the opening paren (in the ZWS)
      const cursorPos = from + 2
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    function handleClosingParenthesis(view, from, to) {
      const { state } = view
      const { doc } = state

      // Overtype: if the next non-ZWS node is an existing group-closing-paren,
      // move past it instead of inserting a duplicate.
      const next = findNextNonZWSNode(doc, from)
      if (next && next.node.type.name === 'group-closing-paren') {
        const tr = state.tr
        const cursorPos = next.pos + next.node.nodeSize
        tr.setSelection(TextSelection.create(tr.doc, cursorPos))
        view.dispatch(tr)
        return true
      }

      if (!isClosingGroup(doc, from)) {
        return false
      }

      const tr = state.tr

      const closingParenNode =
        state.schema.nodes['group-closing-paren'].create()

      tr.replaceWith(from, to, closingParenNode)

      const cursorPos = from + 1
      tr.setSelection(TextSelection.near(tr.doc.resolve(cursorPos)))

      view.dispatch(tr)
      return true
    }

    function isClosingGroup(doc, pos) {
      const $pos = doc.resolve(pos)
      let wrapperStart = 0
      for (let d = $pos.depth; d > 0; d--) {
        if ($pos.node(d).type.name === 'wrapper') {
          wrapperStart = $pos.start(d)
          break
        }
      }

      const stack = buildParenStack(doc, wrapperStart, pos)
      return stack.length > 0 && stack[stack.length - 1] === 'group'
    }

    return [
      new Plugin({
        key: new PluginKey('groupDetection'),
        props: {
          handleTextInput(view, from, to, text) {
            // Process opening parenthesis for group detection
            if (text === '(') {
              return handleOpeningParenthesis(view, from, to)
            }

            // Process closing parenthesis for group detection
            if (text === ')') {
              return handleClosingParenthesis(view, from, to)
            }

            return false
          },
        },
      }),
    ]
  },
})
