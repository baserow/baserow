import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import {
  findClosedStringRangesInNodeMap,
  isInsideClosedStringInNodeMap,
  isAfterUnclosedQuoteInNodeMap,
} from './FormulaExtensionHelpers'

const functionDeletionPluginKey = new PluginKey('functionDeletion')

/**
 * @name FunctionDeletionExtension
 * @description A Tiptap extension that provides "smart" deletion for function
 * calls. When the user presses `Backspace` on a character that is part of a
 * function's syntax (like the parenthesis or a comma), this extension deletes the
 * entire function call, including its arguments, instead of just a single character.
 * This prevents leaving syntactically invalid remnants of a function.
 */
export const FunctionDeletionExtension = Extension.create({
  name: 'functionDeletion',

  addOptions() {
    return {
      functionNames: [],
    }
  },

  addProseMirrorPlugins() {
    const functionNames = this.options.functionNames

    const deleteFunctionRange = (state, view, startPos, endPos) => {
      if (
        startPos < endPos &&
        startPos >= 0 &&
        endPos <= state.doc.content.size
      ) {
        const tr = state.tr.delete(startPos, endPos)
        view.dispatch(tr)
        return true
      }
      return false
    }

    const findFunctionBoundaries = (state, cursorPos, functionNames) => {
      const nodeMap = []
      state.doc.descendants((node, pos) => {
        nodeMap.push({
          node,
          pos,
          end: pos + node.nodeSize,
          isText: node.isText,
          isDataComponent: node.type.name === 'get-formula-component',
          text: node.isText ? node.text : '',
        })
      })

      const stringRanges = findClosedStringRangesInNodeMap(nodeMap)

      const candidates = []

      for (let i = 0; i < nodeMap.length; i++) {
        const item = nodeMap[i]

        if (item.isText && item.text) {
          const functionMatches = [...item.text.matchAll(/(\w+)\(/g)]

          for (const match of functionMatches) {
            const funcName = match[1]
            const matchStart = item.pos + match.index
            const matchEnd = matchStart + match[0].length

            if (!functionNames.includes(funcName)) continue

            // Skip if this function name is inside a string literal (closed or unclosed)
            if (
              isInsideClosedStringInNodeMap(
                nodeMap,
                matchStart,
                stringRanges
              ) ||
              isAfterUnclosedQuoteInNodeMap(nodeMap, matchStart)
            )
              continue

            let openParens = 1
            let closingParenPos = -1

            for (let j = i; j < nodeMap.length && openParens > 0; j++) {
              const searchItem = nodeMap[j]

              if (searchItem.isText && searchItem.text) {
                let textToSearch = searchItem.text
                let textStartPos = searchItem.pos

                if (j === i) {
                  const skipIndex = match.index + match[0].length
                  textToSearch = searchItem.text.substring(skipIndex)
                  textStartPos = searchItem.pos + skipIndex
                }

                for (let k = 0; k < textToSearch.length; k++) {
                  const currentPos = textStartPos + k
                  const char = textToSearch[k]

                  // Only ignore parentheses that are inside CLOSED strings
                  if (
                    !isInsideClosedStringInNodeMap(
                      nodeMap,
                      currentPos,
                      stringRanges
                    )
                  ) {
                    if (char === '(') {
                      openParens++
                    } else if (char === ')') {
                      openParens--
                      if (openParens === 0) {
                        closingParenPos = textStartPos + k + 1
                        break
                      }
                    }
                  }
                }

                if (closingParenPos !== -1) break
              }
            }

            if (closingParenPos !== -1) {
              const isInFunctionRange =
                cursorPos >= matchStart && cursorPos <= closingParenPos

              if (isInFunctionRange) {
                const shouldDelete =
                  (cursorPos >= matchStart + funcName.length &&
                    cursorPos <= matchEnd) ||
                  cursorPos === matchEnd ||
                  cursorPos === closingParenPos

                if (shouldDelete) {
                  candidates.push({
                    start: matchStart,
                    end: closingParenPos,
                    functionName: funcName,
                    size: closingParenPos - matchStart,
                  })
                }
              }
            }
          }
        }
      }

      if (candidates.length > 0) {
        candidates.sort((a, b) => a.size - b.size)
        return candidates[0]
      }

      return null
    }

    const handleFunctionDeletion = (state, view, functionNames) => {
      const { from } = state.selection

      const boundaries = findFunctionBoundaries(state, from, functionNames)

      if (boundaries) {
        return deleteFunctionRange(
          state,
          view,
          boundaries.start,
          boundaries.end
        )
      }

      return false
    }

    return [
      new Plugin({
        key: functionDeletionPluginKey,
        props: {
          handleKeyDown: (view, event) => {
            if (event.key !== 'Backspace') {
              return false
            }

            const { state } = view
            const { selection } = state
            const { from, to } = selection

            if (from !== to) {
              return false
            }

            const nodeAtCursor = state.doc.nodeAt(from - 1)
            if (
              nodeAtCursor &&
              nodeAtCursor.type.name === 'get-formula-component'
            ) {
              return false
            }

            return handleFunctionDeletion(state, view, functionNames)
          },
        },
      }),
    ]
  },
})
