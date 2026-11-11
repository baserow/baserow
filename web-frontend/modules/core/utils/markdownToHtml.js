import MarkdownIt from 'markdown-it'

import {
  preprocessRichTextImages,
  replaceUnresolvedImageRefsWithAlt,
} from '@baserow/modules/core/editor/richTextImageUtils'

// Renders the markdown stored by rich text fields as clean HTML, for the
// `markdown_to_html` runtime formula function. The backend resolves the same
// formulas with `baserow/core/markdown.py`: both sides configure markdown-it
// alike and the rules below are mirrored there, so the same markdown produces
// the same HTML. Neither `renderMarkdown` (a shared parser without these rules)
// nor the grid preview's `parseMarkdown` (UI-only attributes and placeholders)
// fits.

// The CommonJS build exports the class on `default`, the ES build directly.
const Markdown = MarkdownIt?.default || MarkdownIt

const TASK_LIST_MARKERS = ['[ ] ', '[x] ', '[X] ']

/**
 * Port of the `markdown-it-task-lists` core rule with `enabled: false` and
 * `label: false`. The plugin keeps its options in module-level variables that
 * every `md.use()` call overwrites, and the grid preview configures it with
 * labels and enabled checkboxes on each render, so sharing it would change this
 * renderer's output once a preview has rendered. The backend ports the same
 * rule to Python for the same markup.
 */
function taskLists(state) {
  const tokens = state.tokens
  for (let index = 2; index < tokens.length; index++) {
    const token = tokens[index]
    // markdown-it has already trimmed the leading whitespace of the item.
    if (
      token.type !== 'inline' ||
      tokens[index - 1].type !== 'paragraph_open' ||
      tokens[index - 2].type !== 'list_item_open' ||
      !TASK_LIST_MARKERS.some((marker) => token.content.startsWith(marker))
    ) {
      continue
    }

    const checkbox = new state.Token('html_inline', '', 0)
    checkbox.content =
      '<input class="task-list-item-checkbox"' +
      (token.content.startsWith('[ ] ') ? '' : ' checked=""') +
      ' disabled="" type="checkbox">'
    token.children.unshift(checkbox)
    token.children[1].content = token.children[1].content.slice(3)
    token.content = token.content.slice(3)

    const listItem = tokens[index - 2]
    listItem.attrSet('class', 'task-list-item')
    // The enclosing list is the closest previous token one level up.
    for (let parent = index - 3; parent >= 0; parent--) {
      if (tokens[parent].level === listItem.level - 1) {
        tokens[parent].attrSet('class', 'contains-task-list')
        break
      }
    }
  }
}

function renderLinkOpen(tokens, idx, options, env, self) {
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return self.renderToken(tokens, idx, options)
}

// `{ html: false }` on the default preset is what the backend's `js-default`
// preset reproduces: tables and strikethrough on, raw HTML escaped, no linkify,
// no typographer, soft line breaks kept. The parser is stateless once
// configured, so one instance serves every call.
const md = new Markdown({ html: false })
md.core.ruler.after('inline', 'github_task_lists', taskLists)
md.renderer.rules.link_open = renderLinkOpen

/**
 * Converts markdown, such as the value of a rich text field, to HTML.
 *
 * Baserow image references outside code render as `<img>` when they carry a
 * URL (the API form) and as their alt text when they do not: unlike the
 * backend, the browser cannot compute a storage URL from a file name.
 *
 * @param {string} content The markdown to render. Empty and non-string values
 *   render as `''`.
 * @returns {string} The HTML without leading or trailing whitespace.
 */
export function markdownToHtml(content) {
  if (typeof content !== 'string' || !content) return ''
  const { content: withImages } = preprocessRichTextImages(content)
  return md.render(replaceUnresolvedImageRefsWithAlt(withImages)).trim()
}
