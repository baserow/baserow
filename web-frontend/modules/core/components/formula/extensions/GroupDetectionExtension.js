import { Extension } from '@tiptap/core'
import { Plugin, PluginKey, TextSelection } from '@tiptap/pm/state'
import { Fragment } from '@tiptap/pm/model'

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

      // Check if we should create a group parenthesis
      // A group parenthesis is created when:
      // - The previous text does NOT match a known function name

      const textBefore = doc.textBetween(Math.max(0, from - 50), from, ',')

      // If we have function names, check if the text ends with one
      if (functionNames.length > 0) {
        const functionPattern = new RegExp(
          `(^|[^a-zA-Z0-9_])(${functionNames.join('|')})(\\s*)$`,
          'i'
        )

        if (functionPattern.test(textBefore)) {
          // This is a function call, let FunctionDetectionExtension handle it
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

      // Check if we're closing a group by counting parentheses
      if (!isClosingGroup(doc, from)) {
        // Let other extensions handle function closing
        return false
      }

      // This is closing a group
      const tr = state.tr

      // Create the group closing paren node
      const closingParenNode =
        state.schema.nodes['group-closing-paren'].create()

      tr.replaceWith(from, to, closingParenNode)

      // Position cursor after the closing paren
      const cursorPos = from + 1
      tr.setSelection(TextSelection.near(tr.doc.resolve(cursorPos)))

      view.dispatch(tr)
      return true
    }

    function isClosingGroup(doc, pos) {
      // Count parentheses to determine if we're closing a group
      let parenCount = 0
      let foundGroupOpening = false

      // Find the start of the wrapper
      const $pos = doc.resolve(pos)
      let wrapperStart = 0
      for (let d = $pos.depth; d > 0; d--) {
        if ($pos.node(d).type.name === 'wrapper') {
          wrapperStart = $pos.start(d)
          break
        }
      }

      // Traverse from wrapper start to current position
      doc.nodesBetween(wrapperStart, pos, (node, nodePos) => {
        if (nodePos >= pos) return false

        if (node.type.name === 'function-formula-component') {
          parenCount = 1
        } else if (node.type.name === 'group-opening-paren') {
          foundGroupOpening = true
          parenCount++
        } else if (node.type.name === 'group-closing-paren') {
          parenCount--
          if (parenCount === 0) {
            foundGroupOpening = false
          }
        } else if (node.type.name === 'function-closing-paren') {
          parenCount--
        }
      })

      // We're closing a group if we have an open group paren
      return foundGroupOpening && parenCount > 0
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
