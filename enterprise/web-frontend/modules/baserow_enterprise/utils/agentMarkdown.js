import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: false, // Disable HTML tags for security
  linkify: true, // Auto-convert URLs to links
  typographer: true, // Enable smart quotes and other typography
  breaks: false,
})

// Wide tables scroll horizontally inside the message instead of pushing the
// card past the column.
md.renderer.rules.table_open = () =>
  '<div class="agent-chat-message__table"><table>'
md.renderer.rules.table_close = () => '</table></div>'

export function renderMarkdown(content) {
  return md.render(content || '')
}
