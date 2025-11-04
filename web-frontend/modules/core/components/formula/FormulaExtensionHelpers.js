/**
 * @fileoverview Shared utilities for formula editor extensions
 * This module provides common functionality for detecting strings, functions,
 * and other syntactic elements in formula text for use across multiple Tiptap extensions.
 */

// ============================================================================
// String Detection Utilities
// ============================================================================

/**
 * Finds all closed string literal ranges in the document content
 * @param {Array} content - Array of content items with {char, type, docPos, ...}
 * @returns {Array} Array of {start, end} ranges for closed strings
 */
export const findClosedStringRanges = (content) => {
  const ranges = []
  let i = 0

  while (i < content.length) {
    if (content[i].type !== 'text') {
      i++
      continue
    }

    const ch = content[i].char
    if (ch === '"' || ch === "'") {
      const quoteChar = ch
      const startIdx = i
      let escaped = false
      i++

      // Find the closing quote
      while (i < content.length) {
        if (content[i].type !== 'text') {
          i++
          continue
        }

        const currentChar = content[i].char

        if (escaped) {
          escaped = false
          i++
          continue
        }

        if (currentChar === '\\') {
          escaped = true
          i++
          continue
        }

        if (currentChar === quoteChar) {
          // Found closing quote
          ranges.push({ start: startIdx, end: i })
          i++
          break
        }

        i++
      }
    } else {
      i++
    }
  }

  return ranges
}

/**
 * Checks if a position is inside a closed string literal
 * @param {Array} content - Array of content items
 * @param {number} index - Position to check
 * @param {Array} stringRanges - Pre-computed closed string ranges
 * @returns {boolean} True if position is inside a closed string
 */
export const isInsideClosedString = (content, index, stringRanges) => {
  return stringRanges.some((range) => index > range.start && index < range.end)
}

/**
 * Checks if we're currently after an unclosed quote
 * @param {Array} content - Array of content items with {char, type, ...}
 * @param {number} index - Position to check
 * @returns {boolean} True if there's an unclosed quote before this position
 */
export const isAfterUnclosedQuote = (content, index) => {
  let inSingleQuote = false
  let inDoubleQuote = false
  let escaped = false

  for (let idx = 0; idx < index; idx++) {
    if (content[idx].type !== 'text') continue
    const ch = content[idx].char

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

// ============================================================================
// String Detection for NodeMap (used by FunctionDeletionExtension)
// ============================================================================

/**
 * Finds all closed string literal ranges in a nodeMap structure
 * @param {Array} nodeMap - Array of nodes with {pos, text, isText, ...}
 * @returns {Array} Array of {start, end} position ranges for closed strings
 */
export const findClosedStringRangesInNodeMap = (nodeMap) => {
  const ranges = []

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
                i = nodeIdx === nodeMap.indexOf(item) ? k + 1 : item.text.length
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

/**
 * Checks if a position is inside a closed string literal (nodeMap version)
 * @param {Array} nodeMap - Array of nodes
 * @param {number} targetPos - Document position to check
 * @param {Array} stringRanges - Pre-computed closed string ranges
 * @returns {boolean} True if position is inside a closed string
 */
export const isInsideClosedStringInNodeMap = (
  nodeMap,
  targetPos,
  stringRanges
) => {
  return stringRanges.some(
    (range) => targetPos > range.start && targetPos < range.end
  )
}

/**
 * Checks if we're after an unclosed quote (nodeMap version)
 * @param {Array} nodeMap - Array of nodes with {pos, text, isText, ...}
 * @param {number} targetPos - Document position to check
 * @returns {boolean} True if there's an unclosed quote before this position
 */
export const isAfterUnclosedQuoteInNodeMap = (nodeMap, targetPos) => {
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

// ============================================================================
// String Detection for Plain Text (used by FunctionAutoCompleteExtension)
// ============================================================================

/**
 * Checks if cursor is inside a string literal (closed or after unclosed quote)
 * Works on plain text strings (simpler version for autocomplete)
 * @param {string} text - The text to analyze
 * @returns {boolean} True if inside or after an unclosed string
 */
export const isInsideStringInText = (text) => {
  const ranges = []
  let i = 0

  // Find all closed string ranges
  while (i < text.length) {
    const ch = text[i]

    if (ch === '"' || ch === "'") {
      const quoteChar = ch
      const startIdx = i
      let escaped = false
      i++

      // Find the closing quote
      while (i < text.length) {
        const currentChar = text[i]

        if (escaped) {
          escaped = false
          i++
          continue
        }

        if (currentChar === '\\') {
          escaped = true
          i++
          continue
        }

        if (currentChar === quoteChar) {
          // Found closing quote
          ranges.push({ start: startIdx, end: i })
          i++
          break
        }

        i++
      }
    } else {
      i++
    }
  }

  // Check if the last position is inside any closed string range
  const lastPos = text.length - 1
  if (ranges.some((range) => lastPos > range.start && lastPos < range.end)) {
    return true
  }

  // Also check if we're after an unclosed quote
  let inSingleQuote = false
  let inDoubleQuote = false
  let escaped = false

  for (let idx = 0; idx < text.length; idx++) {
    const ch = text[idx]

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

// ============================================================================
// Pattern Matching
// ============================================================================

/**
 * Checks if a pattern matches at a given position in the content
 * @param {Array} content - Array of content items
 * @param {number} index - Starting position
 * @param {string} pattern - Pattern to match
 * @param {boolean} checkWordBoundary - If true, ensures the match is at a word boundary
 * @returns {boolean} True if pattern matches at this position
 */
export const matchesAt = (
  content,
  index,
  pattern,
  checkWordBoundary = false
) => {
  // If checkWordBoundary is true, verify the character before is not alphanumeric
  if (checkWordBoundary && index > 0) {
    const prevItem = content[index - 1]
    if (prevItem && prevItem.type === 'text') {
      const prevChar = prevItem.char
      // Check if previous character is alphanumeric or underscore
      if (/[a-zA-Z0-9_]/.test(prevChar)) {
        return false
      }
    }
  }

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

/**
 * Finds the closing parenthesis for a function, ignoring parentheses in closed strings
 * @param {Array} documentContent - Array of content items
 * @param {number} startIndex - Index after the opening parenthesis
 * @param {Array} stringRanges - Pre-computed closed string ranges
 * @returns {number} Index of closing parenthesis, or -1 if not found
 */
export const findClosingParen = (documentContent, startIndex, stringRanges) => {
  let parenCount = 1
  let k = startIndex

  while (k < documentContent.length && parenCount > 0) {
    if (documentContent[k].type === 'text') {
      // Only count parentheses that are not inside CLOSED strings
      if (!isInsideClosedString(documentContent, k, stringRanges)) {
        if (documentContent[k].char === '(') {
          parenCount++
        } else if (documentContent[k].char === ')') {
          parenCount--
        }
      }
    }
    k++
  }

  return parenCount === 0 ? k - 1 : -1
}
