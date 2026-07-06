import Paragraph from '@tiptap/extension-paragraph'

/**
 * Pads runs of 2+ newlines with one extra newline so that
 * blankLinePreservation can detect the gap on parse.
 */
export function padBlankLinesForMarkdown(text) {
  return text.replace(/\n{2,}/g, (m) => m + '\n')
}

/**
 * Markdown-it plugin that preserves blank lines as empty paragraphs.
 * Detects gaps in token source-line maps and injects empty paragraph
 * tokens for each blank line beyond the standard paragraph separator.
 */
export function blankLinePreservation(md) {
  // parse.setup is called on every parse() — guard against duplicate registration
  if (md._blankLinePreservationInstalled) return
  md._blankLinePreservationInstalled = true

  md.core.ruler.push('preserve_blank_lines', (state) => {
    const tokens = state.tokens
    const newTokens = []
    let lastBlockEnd = null

    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i]

      if (
        token.nesting === 1 &&
        token.map &&
        token.level === 0 &&
        lastBlockEnd !== null
      ) {
        const blankLines = token.map[0] - lastBlockEnd - 1
        for (let j = 0; j < blankLines; j++) {
          newTokens.push(new state.Token('paragraph_open', 'p', 1))
          newTokens.push(new state.Token('paragraph_close', 'p', -1))
        }
      }

      newTokens.push(token)

      if (token.nesting === 1 && token.map && token.level === 0) {
        lastBlockEnd = token.map[1]
      }
    }

    state.tokens = newTokens
  })
}

/**
 * TipTap Paragraph extension that preserves empty paragraphs through
 * the markdown round-trip. Empty paragraphs serialize as extra newlines
 * in markdown, and blankLinePreservation restores them on parse.
 */
export const ParagraphWithEmptyPreservation = Paragraph.extend({
  addStorage() {
    return {
      markdown: {
        serialize(state, node) {
          if (node.childCount === 0) {
            state.write('')
          } else {
            state.renderInline(node)
          }
          state.closeBlock(node)
        },
        parse: {
          setup(markdownit) {
            blankLinePreservation(markdownit)
          },
        },
      },
    }
  },
})
