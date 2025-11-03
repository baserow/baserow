import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from 'prosemirror-state'
import { Decoration, DecorationSet } from 'prosemirror-view'

const functionHighlightPluginKey = new PluginKey('functionHighlight')
/**
 * @name FunctionHighlightExtension
 * @description Provides syntax highlighting for the formula editor. This Tiptap
 * extension scans the editor's content and applies custom CSS classes to function
 * names and operators. It uses ProseMirror's `DecorationSet` to apply inline
 * decorations without modifying the actual document content, ensuring that the
 * highlighting is purely a visual enhancement.
 */
export const FunctionHighlightExtension = Extension.create({
  name: 'functionHighlight',

  addOptions() {
    return {
      functionNames: [],
      operators: [],
    }
  },

  addProseMirrorPlugins() {
    const functionNames = this.options.functionNames
    const operators = this.options.operators

    const matchesAt = (content, index, pattern) => {
      for (let i = 0; i < pattern.length; i++) {
        if (
          index + i >= content.length ||
          content[index + i].type !== 'text' ||
          content[index + i].char.toLowerCase() !== pattern[i].toLowerCase()
        ) {
          return false
        }
      }
      return true
    }

    const addToSegments = (segments, start, end, type, metadata = {}) => {
      // Don't merge function segments - each function should have its own span
      if (type === 'function') {
        segments.push({ start, end, type, ...metadata })
        return
      }

      const existing = segments.find(
        (s) =>
          s.type === type &&
          ((s.start <= start && s.end >= start) ||
            (s.start <= end && s.end >= end) ||
            (start <= s.start && end >= s.start))
      )

      if (existing) {
        existing.start = Math.min(existing.start, start)
        existing.end = Math.max(existing.end, end)
      } else {
        segments.push({ start, end, type, ...metadata })
      }
    }

    const applySegmentDecorations = (segments, text, pos, decorations) => {
      let lastIndex = 0

      segments.forEach((segment) => {
        if (lastIndex < segment.start) {
          const beforeText = text.slice(lastIndex, segment.start)
          if (beforeText.trim()) {
            decorations.push(
              Decoration.inline(pos + lastIndex, pos + segment.start, {
                class: 'text-segment',
              })
            )
          }
        }

        let className
        switch (segment.type) {
          case 'function':
            className = 'function-name-highlight'
            break
          case 'function-paren':
            className = 'function-paren-highlight'
            break
          case 'function-comma':
            className = 'function-comma-highlight'
            break
          case 'operator':
            className = 'operator-highlight'
            break
          default:
            className = 'text-segment'
        }

        decorations.push(
          Decoration.inline(pos + segment.start, pos + segment.end, {
            class: className,
          })
        )

        lastIndex = segment.end
      })

      if (lastIndex < text.length) {
        const remainingText = text.slice(lastIndex)
        if (remainingText.trim()) {
          decorations.push(
            Decoration.inline(pos + lastIndex, pos + text.length, {
              class: 'text-segment',
            })
          )
        }
      }

      if (segments.length === 0 && text.trim()) {
        decorations.push(
          Decoration.inline(pos, pos + text.length, {
            class: 'text-segment',
          })
        )
      }
    }

    return [
      new Plugin({
        key: functionHighlightPluginKey,
        props: {
          decorations(state) {
            const decorations = []
            const doc = state.doc

            const documentContent = []
            doc.descendants((node, pos) => {
              if (node.isText && node.text) {
                for (let i = 0; i < node.text.length; i++) {
                  documentContent.push({
                    char: node.text[i],
                    docPos: pos + i,
                    nodePos: pos,
                    charIndex: i,
                    type: 'text',
                  })
                }
              } else if (node.isLeaf && node.type.name !== 'wrapper') {
                documentContent.push({
                  char: '',
                  docPos: pos,
                  nodePos: pos,
                  charIndex: 0,
                  type: 'component',
                  componentType: node.type.name,
                })
              }
            })

            const functionRanges = []

            for (let i = 0; i < documentContent.length; i++) {
              const content = documentContent[i]
              if (content.type !== 'text') continue

              for (const functionName of functionNames) {
                if (matchesAt(documentContent, i, functionName)) {
                  const functionStart = i
                  let j = i + functionName.length

                  while (
                    j < documentContent.length &&
                    documentContent[j].type === 'text' &&
                    /\s/.test(documentContent[j].char)
                  ) {
                    j++
                  }

                  if (
                    j < documentContent.length &&
                    documentContent[j].type === 'text' &&
                    documentContent[j].char === '('
                  ) {
                    const openParenPos = j
                    let parenCount = 1
                    let k = j + 1

                    while (k < documentContent.length && parenCount > 0) {
                      if (documentContent[k].type === 'text') {
                        if (documentContent[k].char === '(') {
                          parenCount++
                        } else if (documentContent[k].char === ')') {
                          parenCount--
                        }
                      }
                      k++
                    }

                    if (parenCount === 0) {
                      functionRanges.push({
                        name: functionName,
                        start: functionStart,
                        openParen: openParenPos,
                        closeParen: k - 1,
                        end: k,
                      })
                    }
                  }
                }
              }
            }

            doc.descendants((node, pos) => {
              if (node.isText && node.text) {
                const text = node.text
                const segments = []

                // Build function segments for this text node
                for (const funcRange of functionRanges) {
                  let funcStartInText = -1
                  let funcEndInText = -1

                  // Find where this function intersects with the current text node
                  for (let i = 0; i < text.length; i++) {
                    const docPos = pos + i
                    const contentIndex = documentContent.findIndex(
                      (c) => c.docPos === docPos && c.type === 'text'
                    )

                    if (contentIndex === -1) continue

                    // Check if this character is part of the function name or opening parenthesis
                    if (
                      contentIndex >= funcRange.start &&
                      contentIndex <= funcRange.openParen
                    ) {
                      if (funcStartInText === -1) funcStartInText = i
                      funcEndInText = i + 1
                    }
                  }

                  // Add segment for the complete function name + opening parenthesis
                  if (funcStartInText !== -1 && funcEndInText !== -1) {
                    segments.push({
                      start: funcStartInText,
                      end: funcEndInText,
                      type: 'function',
                      functionId: funcRange.start,
                    })
                  }
                }

                // Helper function to check if a position is inside a string literal
                const isInsideString = (textContent, position) => {
                  let inSingleQuote = false
                  let inDoubleQuote = false
                  let escaped = false

                  for (let idx = 0; idx < position; idx++) {
                    const ch = textContent[idx]

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

                  return inSingleQuote || inDoubleQuote
                }

                // Add segments for closing parentheses and commas
                for (let i = 0; i < text.length; i++) {
                  const docPos = pos + i
                  const char = text[i]

                  for (const funcRange of functionRanges) {
                    const contentIndex = documentContent.findIndex(
                      (c) => c.docPos === docPos && c.type === 'text'
                    )

                    if (contentIndex === -1) continue

                    if (contentIndex === funcRange.closeParen) {
                      segments.push({
                        start: i,
                        end: i + 1,
                        type: 'function-paren',
                      })
                    } else if (
                      char === ',' &&
                      contentIndex > funcRange.openParen &&
                      contentIndex < funcRange.closeParen &&
                      !isInsideString(text, i)
                    ) {
                      segments.push({
                        start: i,
                        end: i + 1,
                        type: 'function-comma',
                      })
                    }
                  }
                }

                if (operators.length > 0) {
                  const operatorValues = operators
                    .map((op) => (typeof op === 'string' ? op : op?.operator))
                    .filter((op) => op && typeof op === 'string' && op.trim())

                  if (operatorValues.length > 0) {
                    const escapedOperators = operatorValues
                      .map((op) => op.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
                      .sort((a, b) => b.length - a.length)

                    const operatorPattern = new RegExp(
                      `(${escapedOperators.join('|')})`,
                      'g'
                    )
                    let operatorMatch
                    while (
                      (operatorMatch = operatorPattern.exec(text)) !== null
                    ) {
                      addToSegments(
                        segments,
                        operatorMatch.index,
                        operatorMatch.index + operatorMatch[0].length,
                        'operator'
                      )
                    }
                  }
                }

                segments.sort((a, b) => a.start - b.start)
                applySegmentDecorations(segments, text, pos, decorations)
              }
            })

            return DecorationSet.create(doc, decorations)
          },
        },
      }),
    ]
  },
})
