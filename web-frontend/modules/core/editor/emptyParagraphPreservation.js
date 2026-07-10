import Paragraph from '@tiptap/extension-paragraph'

export function padBlankLinesForMarkdown(text) {
  return text.replace(/\r\n/g, '\n').replace(/\n{2,}/g, (m) => m + '\n')
}

// For container blocks (lists, blockquotes), the token map overshoots past
// trailing blank lines. Walk children to find the real content boundary.
function getContentEnd(tokens, idx) {
  const container = tokens[idx]
  let end = container.map[0]
  for (let j = idx + 1; j < tokens.length; j++) {
    if (tokens[j].level <= container.level) break
    if (tokens[j].type === 'inline' && tokens[j].map) {
      end = tokens[j].map[1]
    }
  }
  return end
}

export function blankLinePreservation(md) {
  if (md._blankLinePreservationInstalled) return
  md._blankLinePreservationInstalled = true

  md.core.ruler.push('preserve_blank_lines', (state) => {
    const tokens = state.tokens
    const newTokens = []
    let lastBlockEnd = null

    for (let i = 0; i < tokens.length; i++) {
      const token = tokens[i]

      if (
        token.nesting >= 0 &&
        token.map &&
        token.level === 0 &&
        lastBlockEnd !== null
      ) {
        const blankLines = Math.max(0, token.map[0] - lastBlockEnd - 1)
        for (let j = 0; j < blankLines; j++) {
          newTokens.push(new state.Token('paragraph_open', 'p', 1))
          newTokens.push(new state.Token('paragraph_close', 'p', -1))
        }
      }

      newTokens.push(token)

      if (token.map && token.level === 0 && token.nesting >= 0) {
        lastBlockEnd =
          token.nesting === 1 ? getContentEnd(tokens, i) : token.map[1]
      }
    }

    state.tokens = newTokens
  })
}

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
