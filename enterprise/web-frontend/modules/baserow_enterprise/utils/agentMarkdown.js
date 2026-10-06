import MarkdownIt from 'markdown-it'

// Raw HTML stays disabled because the content comes from the model.
const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
  breaks: false,
})

// Links open in a new tab so the conversation is not navigated away from;
// `noopener` keeps the opened page from reaching back into this window.
const defaultLinkOpen =
  md.renderer.rules.link_open ||
  ((tokens, idx, options, env, self) => self.renderToken(tokens, idx, options))
md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet('target', '_blank')
  tokens[idx].attrSet('rel', 'noopener noreferrer')
  return defaultLinkOpen(tokens, idx, options, env, self)
}

// Wide tables scroll horizontally inside the message instead of pushing the
// card past the column.
md.renderer.rules.table_open = () =>
  '<div class="agent-chat-message__table"><table>'
md.renderer.rules.table_close = () => '</table></div>'

export function renderMarkdown(content) {
  return md.render(content || '')
}
