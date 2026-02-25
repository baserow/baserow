import { Extension } from '@tiptap/core'
import { Plugin, PluginKey, TextSelection } from '@tiptap/pm/state'
import { Fragment } from '@tiptap/pm/model'
import {
  buildParenStack,
  getTextBeforeCursor,
  findNextNonZWSNode,
} from '@baserow/modules/core/components/formula/extensions/helpers'

/**
 * Unified input detection extension that handles function calls,
 * grouping parentheses, commas, and operators in a single plugin.
 *
 * Replaces the three separate extensions (FunctionDetection,
 * GroupDetection, OperatorDetection) whose implicit ordering via
 * ProseMirror plugin priority was fragile and error-prone.
 */
export const InputDetectionExtension = Extension.create({
  name: 'inputDetection',

  addOptions() {
    return {
      functionNames: [],
      functionDefinitions: {},
      operators: [],
    }
  },

  addProseMirrorPlugins() {
    const { functionNames, functionDefinitions, operators } = this.options

    // ── Shared utilities ──────────────────────────────────────────────

    function getWrapperStart(doc, pos) {
      const $pos = doc.resolve(pos)
      for (let d = $pos.depth; d > 0; d--) {
        if ($pos.node(d).type.name === 'wrapper') {
          return $pos.start(d)
        }
      }
      return null
    }

    function getParenStackTop(doc, pos) {
      const wrapperStart = getWrapperStart(doc, pos)
      if (wrapperStart === null) return null
      const stack = buildParenStack(doc, wrapperStart, pos)
      return stack.length > 0 ? stack[stack.length - 1] : null
    }

    function isInsideStringLiteral(doc, pos) {
      const contextStart = Math.max(0, pos - 200)
      const textBefore = doc.textBetween(contextStart, pos, ' ')

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

      return singleQuoteCount % 2 === 1 || doubleQuoteCount % 2 === 1
    }

    // ── Opening parenthesis ───────────────────────────────────────────

    function handleOpenParen(view, from, to) {
      return tryFunctionOpen(view, from, to) || handleGroupOpen(view, from, to)
    }

    function tryFunctionOpen(view, from, to) {
      const { state } = view
      const { doc } = state

      if (functionNames.length === 0) return false

      const textBefore = getTextBeforeCursor(doc, from)

      const functionPattern = new RegExp(
        `(^|[^a-zA-Z])(${functionNames.join('|')})(\\s*)$`,
        'i'
      )
      const match = textBefore.match(functionPattern)
      if (!match) return false

      const functionName = match[2]
      const spacesBeforeParenthesis = match[3] || ''
      const functionStart =
        from - functionName.length - spacesBeforeParenthesis.length

      const functionDef = functionDefinitions[functionName.toLowerCase()]
      if (!functionDef) return false

      const signature = functionDef.signature || {}
      const minArgs = signature.minArgs || 0
      const tr = state.tr

      const nodesToInsert = []
      nodesToInsert.push(state.schema.text('\u200B'))

      nodesToInsert.push(
        state.schema.nodes['function-formula-component'].create({
          functionName,
          hasNoArgs: minArgs === 0,
        })
      )

      if (minArgs > 0) {
        nodesToInsert.push(state.schema.text('\u200B'))
        for (let i = 1; i < minArgs; i++) {
          nodesToInsert.push(
            state.schema.nodes['function-argument-comma'].create()
          )
          nodesToInsert.push(state.schema.text('\u200B'))
        }
      }

      nodesToInsert.push(
        state.schema.nodes['function-closing-paren'].create({
          noArgs: minArgs === 0,
        })
      )
      nodesToInsert.push(state.schema.text('\u200B'))

      tr.replaceWith(functionStart, to, Fragment.from(nodesToInsert))

      const cursorPos =
        minArgs === 0 ? functionStart + 3 : functionStart + 2
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    function handleGroupOpen(view, from, to) {
      const { state } = view
      const tr = state.tr

      const nodesToInsert = [
        state.schema.text('\u200B'),
        state.schema.nodes['group-opening-paren'].create(),
        state.schema.text('\u200B'),
      ]

      tr.replaceWith(from, to, Fragment.from(nodesToInsert))

      const cursorPos = from + 2
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    // ── Closing parenthesis ───────────────────────────────────────────

    function handleCloseParen(view, from, to) {
      const { state } = view
      const { doc } = state

      // Overtype: skip past an existing closing paren instead of
      // inserting a duplicate that would corrupt the paren stack.
      const next = findNextNonZWSNode(doc, from)
      if (
        next &&
        (next.node.type.name === 'function-closing-paren' ||
          next.node.type.name === 'group-closing-paren')
      ) {
        const tr = state.tr
        const cursorPos = next.pos + next.node.nodeSize
        tr.setSelection(TextSelection.create(tr.doc, cursorPos))
        view.dispatch(tr)
        return true
      }

      if (isInsideStringLiteral(doc, from)) return false

      const stackTop = getParenStackTop(doc, from)

      if (stackTop === 'function') {
        const tr = state.tr
        const closingNode =
          state.schema.nodes['function-closing-paren'].create()
        tr.replaceWith(from, to, closingNode)
        const cursorPos = from + 1
        tr.setSelection(
          state.selection.constructor.near(tr.doc.resolve(cursorPos))
        )
        view.dispatch(tr)
        return true
      }

      if (stackTop === 'group') {
        const tr = state.tr
        const closingNode =
          state.schema.nodes['group-closing-paren'].create()
        tr.replaceWith(from, to, closingNode)
        const cursorPos = from + 1
        tr.setSelection(TextSelection.near(tr.doc.resolve(cursorPos)))
        view.dispatch(tr)
        return true
      }

      return false
    }

    // ── Comma ─────────────────────────────────────────────────────────

    function handleComma(view, from, to) {
      const { state } = view
      const { doc } = state

      if (getParenStackTop(doc, from) !== 'function') return false
      if (isInsideStringLiteral(doc, from)) return false

      const tr = state.tr
      const nodesToInsert = [
        state.schema.nodes['function-argument-comma'].create(),
        state.schema.text('\u200B'),
      ]

      tr.replaceWith(from, to, Fragment.from(nodesToInsert))

      const cursorPos = from + 1
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    // ── Operators ─────────────────────────────────────────────────────

    function handleMinusWithSpace(view, from) {
      const { state } = view
      const { doc, schema, tr } = state

      const $pos = doc.resolve(from)
      const nodeBefore = $pos.nodeBefore

      if (
        !nodeBefore ||
        !nodeBefore.isText ||
        !nodeBefore.text ||
        !nodeBefore.text.endsWith('-')
      ) {
        return false
      }

      const minusStartPos = from - 1
      const nodesToInsert = [
        schema.nodes['operator-formula-component'].create({
          operatorSymbol: '-',
        }),
        schema.text(' '),
        schema.text('\u200B'),
      ]

      tr.replaceWith(minusStartPos, from, Fragment.from(nodesToInsert))

      const cursorPos = minusStartPos + 2
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    function handleOperator(view, from, to, typedText) {
      const { state } = view
      const { doc, tr, schema } = state

      if (isInsideStringLiteral(doc, from)) return false

      let operatorText = typedText
      let startPos = from
      let endPos = from

      const $pos = doc.resolve(from)
      const nodeBefore = $pos.nodeBefore

      if (
        nodeBefore &&
        nodeBefore.type.name === 'operator-formula-component'
      ) {
        const potential = nodeBefore.attrs.operatorSymbol + typedText
        if (operators.includes(potential)) {
          operatorText = potential
          startPos = from - nodeBefore.nodeSize
          endPos = from
        }
      } else {
        const prevChar = doc.textBetween(Math.max(0, from - 1), from, '')
        const potential = prevChar + typedText

        if (prevChar && operators.includes(potential)) {
          operatorText = potential
          startPos = from - 1
          endPos = from
        } else if (operators.includes(typedText)) {
          operatorText = typedText
        }
      }

      if (!operators.includes(operatorText)) return false

      const operatorNode = schema.nodes['operator-formula-component'].create({
        operatorSymbol: operatorText,
      })

      tr.replaceWith(
        startPos,
        endPos,
        Fragment.from([operatorNode, schema.text('\u200B')])
      )

      const cursorPos = startPos + 1
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    // ── Operator character set ────────────────────────────────────────

    const operatorChars = new Set()
    operators.forEach((op) => {
      for (const ch of op) operatorChars.add(ch)
    })

    // ── Single plugin ─────────────────────────────────────────────────

    return [
      new Plugin({
        key: new PluginKey('inputDetection'),
        props: {
          handleTextInput(view, from, to, text) {
            if (text === '(') return handleOpenParen(view, from, to)
            if (text === ')') return handleCloseParen(view, from, to)
            if (text === ',') return handleComma(view, from, to)
            if (text === '-') return false
            if (text === ' ') return handleMinusWithSpace(view, from)
            if (operatorChars.has(text))
              return handleOperator(view, from, to, text)
            return false
          },
        },
      }),
    ]
  },
})
