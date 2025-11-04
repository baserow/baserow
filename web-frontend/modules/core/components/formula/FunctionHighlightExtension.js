import { Extension } from '@tiptap/core'
import { Plugin, PluginKey } from 'prosemirror-state'
import { Decoration, DecorationSet } from 'prosemirror-view'
import {
  findClosedStringRanges,
  isInsideClosedString,
  isAfterUnclosedQuote,
  matchesAt,
  findClosingParen,
} from './FormulaExtensionHelpers'

const functionHighlightPluginKey = new PluginKey('functionHighlight')

// ============================================================================
// Function Detection
// ============================================================================

/**
 * Finds all complete function ranges in the document
 */
const findFunctionRanges = (documentContent, functionNames, stringRanges) => {
  const functionRanges = []

  for (let i = 0; i < documentContent.length; i++) {
    const content = documentContent[i]
    if (content.type !== 'text') continue

    // Skip if we're inside a string literal (closed or unclosed)
    if (
      isInsideClosedString(documentContent, i, stringRanges) ||
      isAfterUnclosedQuote(documentContent, i)
    ) {
      continue
    }

    for (const functionName of functionNames) {
      if (matchesAt(documentContent, i, functionName, true)) {
        const functionStart = i
        let j = i + functionName.length

        // Skip whitespace after function name
        while (
          j < documentContent.length &&
          documentContent[j].type === 'text' &&
          /\s/.test(documentContent[j].char)
        ) {
          j++
        }

        // Check for opening parenthesis
        if (
          j < documentContent.length &&
          documentContent[j].type === 'text' &&
          documentContent[j].char === '('
        ) {
          const openParenPos = j
          const closeParen = findClosingParen(
            documentContent,
            j + 1,
            stringRanges
          )

          // Only add function range if it's complete
          if (closeParen !== -1) {
            functionRanges.push({
              name: functionName,
              start: functionStart,
              openParen: openParenPos,
              closeParen,
              end: closeParen + 1,
            })
          }
        }
      }
    }
  }

  return functionRanges
}

// ============================================================================
// Segment Building
// ============================================================================

/**
 * Finds the content index for a document position
 */
const findContentIndex = (documentContent, docPos) => {
  return documentContent.findIndex(
    (c) => c.docPos === docPos && c.type === 'text'
  )
}

/**
 * Builds highlighting segments for a text node
 */
const buildSegments = (
  text,
  pos,
  documentContent,
  functionRanges,
  operators,
  stringRanges
) => {
  const segments = []

  // Build function name segments
  for (const funcRange of functionRanges) {
    let funcStartInText = -1
    let funcEndInText = -1

    for (let i = 0; i < text.length; i++) {
      const contentIndex = findContentIndex(documentContent, pos + i)
      if (contentIndex === -1) continue

      if (
        contentIndex >= funcRange.start &&
        contentIndex <= funcRange.openParen
      ) {
        if (funcStartInText === -1) funcStartInText = i
        funcEndInText = i + 1
      }
    }

    if (funcStartInText !== -1 && funcEndInText !== -1) {
      segments.push({
        start: funcStartInText,
        end: funcEndInText,
        type: 'function',
        functionId: funcRange.start,
      })
    }
  }

  // Build segments for closing parentheses and commas
  for (let i = 0; i < text.length; i++) {
    const char = text[i]
    const contentIndex = findContentIndex(documentContent, pos + i)

    for (const funcRange of functionRanges) {
      if (contentIndex === -1) continue

      // Highlight closing paren
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
        !isInsideClosedString(documentContent, contentIndex, stringRanges) &&
        !isAfterUnclosedQuote(documentContent, contentIndex)
      ) {
        segments.push({
          start: i,
          end: i + 1,
          type: 'function-comma',
        })
      }
    }
  }

  // Build operator segments
  if (operators.length > 0) {
    const operatorValues = operators
      .map((op) => (typeof op === 'string' ? op : op?.operator))
      .filter((op) => op && typeof op === 'string' && op.trim())

    if (operatorValues.length > 0) {
      const escapedOperators = operatorValues
        .map((op) => op.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
        .sort((a, b) => b.length - a.length)

      const operatorPattern = new RegExp(`(${escapedOperators.join('|')})`, 'g')

      let operatorMatch
      while ((operatorMatch = operatorPattern.exec(text)) !== null) {
        const contentIndex = findContentIndex(
          documentContent,
          pos + operatorMatch.index
        )

        if (
          contentIndex !== -1 &&
          !isInsideClosedString(documentContent, contentIndex, stringRanges) &&
          !isAfterUnclosedQuote(documentContent, contentIndex)
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
  }

  return segments
}

/**
 * Merges overlapping segments
 */
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

/**
 * Gets the CSS class for a segment type
 */
const getSegmentClassName = (segmentType) => {
  switch (segmentType) {
    case 'function':
      return 'function-name-highlight'
    case 'function-paren':
      return 'function-paren-highlight'
    case 'function-comma':
      return 'function-comma-highlight'
    case 'operator':
      return 'operator-highlight'
    default:
      return 'text-segment'
  }
}

/**
 * Applies decorations for segments
 */
const applySegmentDecorations = (segments, text, pos, decorations) => {
  let lastIndex = 0

  segments.forEach((segment) => {
    // Add decoration for text before this segment
    if (lastIndex < segment.start) {
      const beforeText = text.slice(lastIndex, segment.start)
      // Create text-segment even for whitespace-only text to provide visual cursor placement
      if (beforeText) {
        decorations.push(
          Decoration.inline(pos + lastIndex, pos + segment.start, {
            class: 'text-segment',
          })
        )
      }
    }

    // Add decoration for the segment itself
    decorations.push(
      Decoration.inline(pos + segment.start, pos + segment.end, {
        class: getSegmentClassName(segment.type),
      })
    )

    lastIndex = segment.end
  })

  // Add decoration for remaining text
  if (lastIndex < text.length) {
    const remainingText = text.slice(lastIndex)
    // Create text-segment even for whitespace-only text to provide visual cursor placement
    if (remainingText) {
      decorations.push(
        Decoration.inline(pos + lastIndex, pos + text.length, {
          class: 'text-segment',
        })
      )
    }
  }

  // If no segments, decorate entire text
  if (segments.length === 0 && text) {
    decorations.push(
      Decoration.inline(pos, pos + text.length, {
        class: 'text-segment',
      })
    )
  }
}

// ============================================================================
// Main Extension
// ============================================================================
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

            const stringRanges = findClosedStringRanges(documentContent)
            const functionRanges = findFunctionRanges(
              documentContent,
              functionNames,
              stringRanges
            )

            doc.descendants((node, pos) => {
              if (node.isText && node.text) {
                const segments = buildSegments(
                  node.text,
                  pos,
                  documentContent,
                  functionRanges,
                  operators,
                  stringRanges
                )

                segments.sort((a, b) => a.start - b.start)
                applySegmentDecorations(segments, node.text, pos, decorations)
              }
            })

            return DecorationSet.create(doc, decorations)
          },
        },
      }),
    ]
  },
})
