import { Extension } from '@tiptap/core'
import { Plugin, PluginKey, TextSelection } from '@tiptap/pm/state'
import { Fragment } from '@tiptap/pm/model'
import {
  buildParenStack,
  getTextBeforeCursor,
  findNextNonZWSNode,
  findInnermostUnclosedFunctionNode,
  findPendingTextFunctionOpen,
  zwsTextNode,
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

    function areParensBalanced(doc, type) {
      let openers = 0
      let closers = 0
      const openerName =
        type === 'function'
          ? 'function-formula-component'
          : 'group-opening-paren'
      const closerName =
        type === 'function' ? 'function-closing-paren' : 'group-closing-paren'
      doc.descendants((node) => {
        if (node.type.name === openerName) openers++
        else if (node.type.name === closerName) closers++
      })
      return openers <= closers
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
      if (isInsideStringLiteral(view.state.doc, from)) return false
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
      nodesToInsert.push(zwsTextNode(state.schema))

      nodesToInsert.push(
        state.schema.nodes['function-formula-component'].create({
          functionName,
          hasNoArgs: minArgs === 0,
        })
      )

      if (minArgs > 0) {
        nodesToInsert.push(zwsTextNode(state.schema))
        for (let i = 1; i < minArgs; i++) {
          nodesToInsert.push(
            state.schema.nodes['function-argument-comma'].create()
          )
          nodesToInsert.push(zwsTextNode(state.schema))
        }
      }

      nodesToInsert.push(
        state.schema.nodes['function-closing-paren'].create({
          noArgs: minArgs === 0,
        })
      )
      nodesToInsert.push(zwsTextNode(state.schema))

      tr.replaceWith(functionStart, to, Fragment.from(nodesToInsert))

      const cursorPos = minArgs === 0 ? functionStart + 3 : functionStart + 2
      tr.setSelection(TextSelection.create(tr.doc, cursorPos))

      view.dispatch(tr)
      return true
    }

    function handleGroupOpen(view, from, to) {
      const { state } = view
      const tr = state.tr

      const nodesToInsert = [
        zwsTextNode(state.schema),
        state.schema.nodes['group-opening-paren'].create(),
        zwsTextNode(state.schema),
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

      if (isInsideStringLiteral(doc, from)) return false

      const stackTop = getParenStackTop(doc, from)

      // Overtype: skip past an existing closing paren instead of inserting
      // a duplicate. Three conditions must all be met:
      //  1. The next non-ZWS node is a closing paren
      //  2. Its type matches the stack top (function↔function, group↔group)
      //  3. Parens of that type are balanced in the document (no missing closer)
      const next = findNextNonZWSNode(doc, from)
      if (next) {
        const isMatchingFunction =
          stackTop === 'function' &&
          next.node.type.name === 'function-closing-paren'
        const isMatchingGroup =
          stackTop === 'group' && next.node.type.name === 'group-closing-paren'

        if (
          (isMatchingFunction || isMatchingGroup) &&
          areParensBalanced(doc, stackTop)
        ) {
          const tr = state.tr
          const cursorPos = next.pos + next.node.nodeSize
          tr.setSelection(TextSelection.create(tr.doc, cursorPos))
          view.dispatch(tr)
          return true
        }
      }

      // When the nearest unclosed `(` is a plain-text `(` preceded by a
      // known function name (typically coming from pasted-but-unparseable
      // content like `...+month(`), promote it to a proper function node
      // and close it with a function-closing-paren — so the whole call
      // becomes highlighted once the user closes it.
      const wrapperStart = getWrapperStart(doc, from)
      if (wrapperStart !== null) {
        const pending = findPendingTextFunctionOpen(
          doc,
          wrapperStart,
          from,
          functionNames
        )
        if (pending) {
          return upgradeTextFunctionOnClose(view, pending, from, to)
        }
      }

      // Insert a new closing paren only when the opener doesn't have its
      // closer yet. If parens are already balanced (e.g. typing ')' at an
      // argument position inside `if(|, , )`), skip to avoid duplicates.
      if (stackTop === 'function' && !areParensBalanced(doc, 'function')) {
        // Mirror the `tryFunctionOpen` behaviour: if the unclosed opener
        // is a 0-arg function and nothing (beyond ZWS) sits between it
        // and the typed ')', tag the closing paren with `noArgs: true`
        // so styling (tight spacing, paren-highlight) stays consistent.
        const innermost =
          wrapperStart !== null
            ? findInnermostUnclosedFunctionNode(
                doc,
                wrapperStart,
                from,
                functionNames
              )
            : null
        let isNoArgsCall = false
        if (innermost && innermost.node?.attrs?.hasNoArgs) {
          const between = doc
            .textBetween(innermost.nodeEnd, from, '\uFFFD')
            .replace(/\u200B/g, '')
          isNoArgsCall = between.length === 0
        }

        const tr = state.tr
        const closingNode = state.schema.nodes['function-closing-paren'].create(
          {
            noArgs: isNoArgsCall,
          }
        )
        tr.replaceWith(from, to, closingNode)
        const cursorPos = from + 1
        tr.setSelection(
          state.selection.constructor.near(tr.doc.resolve(cursorPos))
        )
        view.dispatch(tr)
        return true
      }

      if (stackTop === 'group' && !areParensBalanced(doc, 'group')) {
        const tr = state.tr
        const closingNode = state.schema.nodes['group-closing-paren'].create()
        tr.replaceWith(from, to, closingNode)
        const cursorPos = from + 1
        tr.setSelection(TextSelection.near(tr.doc.resolve(cursorPos)))
        view.dispatch(tr)
        return true
      }

      // Fallback: insert a group-closing-paren so ')' is always highlighted
      // in mauve — whether typed standalone, inside a balanced function, or
      // inside a balanced group.
      const tr = state.tr
      const closingNode = state.schema.nodes['group-closing-paren'].create()
      tr.replaceWith(from, to, closingNode)
      const cursorPos = from + 1
      tr.setSelection(TextSelection.near(tr.doc.resolve(cursorPos)))
      view.dispatch(tr)
      return true
    }

    function upgradeTextFunctionOnClose(view, pending, from, to) {
      const { state } = view
      const { doc, schema } = state
      const { functionName, functionStart, parenEnd } = pending
      const functionDef = functionDefinitions[functionName.toLowerCase()]
      const minArgs = functionDef?.signature?.minArgs || 0

      // Treat the call as a no-args invocation only when the function
      // takes no arguments AND nothing (beyond ZWS markers) sits between
      // the `(` and the typed `)`. `\uFFFD` stands in for any atom node
      // between those positions, keeping the check robust against
      // already-parsed content like operator components.
      const betweenText = doc
        .textBetween(parenEnd, from, '\uFFFD')
        .replace(/\u200B/g, '')
      const isNoArgsCall = minArgs === 0 && betweenText.length === 0

      const tr = state.tr

      // Apply the higher-position replacement first so positions below
      // remain stable while we build the transaction.
      tr.replaceWith(
        from,
        to,
        Fragment.from([
          schema.nodes['function-closing-paren'].create({
            noArgs: isNoArgsCall,
          }),
          zwsTextNode(schema),
        ])
      )
      tr.replaceWith(
        functionStart,
        parenEnd,
        Fragment.from([
          zwsTextNode(schema),
          schema.nodes['function-formula-component'].create({
            functionName,
            hasNoArgs: isNoArgsCall,
          }),
        ])
      )

      // Place the cursor right after the closing paren (before its
      // trailing ZWS). `to` maps forward through both replacements to
      // that position in the final document.
      const cursorPos = tr.mapping.map(to, 1)
      tr.setSelection(TextSelection.near(tr.doc.resolve(cursorPos)))

      view.dispatch(tr)
      return true
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
        zwsTextNode(state.schema),
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
        zwsTextNode(schema),
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

      if (nodeBefore && nodeBefore.type.name === 'operator-formula-component') {
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
        Fragment.from([operatorNode, zwsTextNode(schema)])
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
