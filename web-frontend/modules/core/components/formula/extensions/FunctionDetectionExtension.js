import { Extension } from '@tiptap/core'
import { Plugin, PluginKey, TextSelection } from '@tiptap/pm/state'
import { Fragment } from '@tiptap/pm/model'
import {
  buildParenStack,
  getTextBeforeCursor,
  findNextNonZWSNode,
} from '@baserow/modules/core/components/formula/extensions/helpers'

export const FunctionDetectionExtension = Extension.create({
  name: 'functionDetection',

  addOptions() {
    return {
      functionNames: [],
      functionDefinitions: {},
    }
  },

  addProseMirrorPlugins() {
    const functionNames = this.options.functionNames
    const functionDefinitions = this.options.functionDefinitions

    function handleOpeningParenthesis(view, from, to) {
      const { state } = view
      const { doc } = state

      const textBefore = getTextBeforeCursor(doc, from)

      const functionPattern = new RegExp(
        `(^|[^a-zA-Z])(${functionNames.join('|')})(\\s*)$`,
        'i'
      )
      const match = textBefore.match(functionPattern)

      if (match) {
        const functionName = match[2]
        const spacesBeforeParenthesis = match[3] || ''
        const functionStart =
          from - functionName.length - spacesBeforeParenthesis.length

        // Find the function definition using the pre-computed map
        const functionDef = functionDefinitions[functionName.toLowerCase()]

        if (functionDef) {
          const signature = functionDef.signature || {}
          const minArgs = signature.minArgs || 0

          // Create a transaction to replace the function text with the component
          const tr = state.tr

          // Build all nodes to insert
          const nodesToInsert = []

          // Add ZWS before the function component
          nodesToInsert.push(state.schema.text('\u200B'))

          // Insert function node (atomic)
          const functionNode = state.schema.nodes[
            'function-formula-component'
          ].create({
            functionName,
            hasNoArgs: minArgs === 0,
          })
          nodesToInsert.push(functionNode)

          if (minArgs > 0) {
            nodesToInsert.push(state.schema.text('\u200B')) // First argument
            for (let i = 1; i < minArgs; i++) {
              nodesToInsert.push(
                state.schema.nodes['function-argument-comma'].create()
              )
              nodesToInsert.push(state.schema.text('\u200B')) // Subsequent arguments
            }
          }

          // Insert the closing parenthesis as atomic node
          const closingParenNode = state.schema.nodes[
            'function-closing-paren'
          ].create({
            noArgs: minArgs === 0,
          })
          nodesToInsert.push(closingParenNode)

          // Always add a ZWS after the whole function call
          // CleanupZWSExtension will remove any consecutive ZWS automatically
          nodesToInsert.push(state.schema.text('\u200B'))

          // Insert all nodes at once using Fragment.from
          const fragment = Fragment.from(nodesToInsert)

          // Replace the function name + opening parenthesis with our nodes
          tr.replaceWith(functionStart, to, fragment)

          // Position cursor:
          // - If no arguments expected, place after closing paren (but before the final ZWS)
          // - Otherwise, place right after the function component (in first argument slot)
          let cursorPos
          if (minArgs === 0) {
            // ZWS (1) + functionNode (1) + closingParenNode (1) = 3
            // We place cursor at position 3, which is after the closing paren but before the final ZWS
            cursorPos = functionStart + 3
          } else {
            // ZWS (1) + functionNode (1) = 2 (in first argument slot)
            cursorPos = functionStart + 2
          }

          tr.setSelection(TextSelection.create(tr.doc, cursorPos))

          // Apply the transaction
          view.dispatch(tr)
          return true
        }
      }

      return false
    }

    function handleComma(view, from, to) {
      const { state } = view
      const { doc } = state

      // Check if we're inside a function
      if (!isInsideFunction(doc, from)) {
        return false
      }

      // Check if we're inside a string literal
      if (isInsideStringLiteral(doc, from)) {
        return false
      }

      // Create transaction
      const tr = state.tr

      // Create the atomic comma node and a ZWS for the next argument
      const nodesToInsert = [
        state.schema.nodes['function-argument-comma'].create(),
        state.schema.text('\u200B'),
      ]
      const fragment = Fragment.from(nodesToInsert)

      // Replace the typed comma with the atomic node
      tr.replaceWith(from, to, fragment)

      // Position cursor after the comma, in the new ZWS slot
      const cursorPos = from + 1
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    function isInsideFunction(doc, pos) {
      const $pos = doc.resolve(pos)

      let wrapperStart = null
      for (let d = $pos.depth; d > 0; d--) {
        if ($pos.node(d).type.name === 'wrapper') {
          wrapperStart = $pos.start(d)
          break
        }
      }

      if (wrapperStart === null) return false

      const stack = buildParenStack(doc, wrapperStart, pos)
      return stack.length > 0 && stack[stack.length - 1] === 'function'
    }

    function isInsideStringLiteral(doc, pos) {
      // Get text from start of current context to cursor position
      const contextStart = Math.max(0, pos - 200) // Look back up to 200 chars
      const textBefore = doc.textBetween(contextStart, pos, ' ')

      // Count quotes to determine if we're inside a string
      let singleQuoteCount = 0
      let doubleQuoteCount = 0
      let escaped = false

      for (let i = 0; i < textBefore.length; i++) {
        const char = textBefore[i]

        if (escaped) {
          escaped = false
          continue
        }

        if (char === '\\') {
          escaped = true
        } else if (char === "'") {
          singleQuoteCount++
        } else if (char === '"') {
          doubleQuoteCount++
        }
      }

      // If odd number of quotes, we're inside a string
      return singleQuoteCount % 2 === 1 || doubleQuoteCount % 2 === 1
    }

    function handleClosingParenthesis(view, from, to) {
      const { state } = view
      const { doc } = state

      // Overtype: if the next non-ZWS node is an existing function-closing-paren
      // (auto-generated when the function was created), skip past it instead of
      // inserting a duplicate that would corrupt the paren stack.
      const next = findNextNonZWSNode(doc, from)
      if (next && next.node.type.name === 'function-closing-paren') {
        const tr = state.tr
        const cursorPos = next.pos + next.node.nodeSize
        tr.setSelection(TextSelection.create(tr.doc, cursorPos))
        view.dispatch(tr)
        return true
      }

      if (!isClosingFunction(doc, from)) {
        return false
      }

      if (isInsideStringLiteral(doc, from)) {
        return false
      }

      const tr = state.tr
      const closingParenNode =
        state.schema.nodes['function-closing-paren'].create()

      tr.replaceWith(from, to, closingParenNode)

      const cursorPos = from + 1
      tr.setSelection(
        state.selection.constructor.near(tr.doc.resolve(cursorPos))
      )

      view.dispatch(tr)
      return true
    }

    function isClosingFunction(doc, pos) {
      const $pos = doc.resolve(pos)

      let wrapperStart = null
      for (let d = $pos.depth; d > 0; d--) {
        if ($pos.node(d).type.name === 'wrapper') {
          wrapperStart = $pos.start(d)
          break
        }
      }

      if (wrapperStart === null) return false

      const stack = buildParenStack(doc, wrapperStart, pos)
      return stack.length > 0 && stack[stack.length - 1] === 'function'
    }

    return [
      new Plugin({
        key: new PluginKey('functionDetection'),
        props: {
          handleTextInput(view, from, to, text) {
            // Process opening parenthesis for function detection
            if (text === '(') {
              return handleOpeningParenthesis(view, from, to)
            }

            // Process comma for argument separation
            if (text === ',') {
              return handleComma(view, from, to)
            }

            // Process closing parenthesis
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
