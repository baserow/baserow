import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from '@tiptap/pm/state'

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

      // Helper function to find all closed string literal ranges
      const findClosedStringRanges = (nodeMap) => {
        const ranges = []
        let currentPos = 0

        for (const item of nodeMap) {
          if (item.isText && item.text) {
            let i = 0
            while (i < item.text.length) {
              const ch = item.text[i]
              const charPos = item.pos + i

              if (ch === '"' || ch === "'") {
                const quoteChar = ch
                const startPos = charPos
                let escaped = false
                i++

                // Find the closing quote in this or subsequent nodes
                let found = false
                for (
                  let nodeIdx = nodeMap.indexOf(item);
                  nodeIdx < nodeMap.length;
                  nodeIdx++
                ) {
                  const searchItem = nodeMap[nodeIdx]
                  if (!searchItem.isText || !searchItem.text) {
                    if (nodeIdx > nodeMap.indexOf(item)) break
                    continue
                  }

                  const startIdx = nodeIdx === nodeMap.indexOf(item) ? i : 0
                  for (let k = startIdx; k < searchItem.text.length; k++) {
                    const currentChar = searchItem.text[k]
                    const currentCharPos = searchItem.pos + k

                    if (escaped) {
                      escaped = false
                      continue
                    }

                    if (currentChar === '\\') {
                      escaped = true
                      continue
                    }

                    if (currentChar === quoteChar) {
                      ranges.push({ start: startPos, end: currentCharPos })
                      i =
                        nodeIdx === nodeMap.indexOf(item)
                          ? k + 1
                          : item.text.length
                      found = true
                      break
                    }
                  }

                  if (found) break
                }

                if (!found) {
                  // No closing quote found, skip to next char
                  break
                }
              } else {
                i++
              }
            }
          }
        }

        return ranges
      }

      // Helper function to check if a position is inside a closed string literal
      const isInsideClosedString = (nodeMap, targetPos, stringRanges) => {
        return stringRanges.some(
          (range) => targetPos > range.start && targetPos < range.end
        )
      }

      // Helper function to check if we're after an unclosed quote
      const isAfterUnclosedQuote = (nodeMap, targetPos) => {
        let inSingleQuote = false
        let inDoubleQuote = false
        let escaped = false

        for (const item of nodeMap) {
          if (item.isText && item.text) {
            for (let idx = 0; idx < item.text.length; idx++) {
              const currentPos = item.pos + idx

              if (currentPos >= targetPos) {
                return inSingleQuote || inDoubleQuote
              }

              const ch = item.text[idx]

              if (escaped) {
                escaped = false
                continue
              }

              if (ch === '\\') {
                escaped = true
                continue
              }

              if (ch === "'" && !inDoubleQuote) {
                inSingleQuote = !inSingleQuote
              } else if (ch === '"' && !inSingleQuote) {
                inDoubleQuote = !inDoubleQuote
              }
            }
          }
        }

        return inSingleQuote || inDoubleQuote
      }

      const stringRanges = findClosedStringRanges(nodeMap)

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
              isInsideClosedString(nodeMap, matchStart, stringRanges) ||
              isAfterUnclosedQuote(nodeMap, matchStart)
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
                    !isInsideClosedString(nodeMap, currentPos, stringRanges)
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
