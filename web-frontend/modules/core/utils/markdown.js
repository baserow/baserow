import MarkdownIt from 'markdown-it'

// One markdown-it parser for the whole app. Creating one per component adds up
// when many small texts render at once, e.g. the cells of a table. Rendering is
// synchronous, so `renderMarkdown` configures the shared parser, uses it and
// restores it before any other caller (or, on the server, any other request)
// can touch it.
const Markdown = MarkdownIt?.default || MarkdownIt
const md = new Markdown()
const baseRules = { ...md.renderer.rules }

/**
 * Renders markdown to HTML with the shared parser.
 *
 * @param {string} content The markdown to render.
 * @param {Object} [options]
 * @param {Object} [options.rules] Renderer rules merged over the defaults, e.g.
 *   to add CSS classes to the rendered tags.
 * @param {boolean} [options.inline] Only the inline syntax (emphasis, links,
 *   code, ...) applies and the result has no wrapping paragraph.
 * @param {string[]} [options.disabledRules] Names of markdown-it rules to
 *   switch off, e.g. `['image', 'link']`. Unknown names are ignored.
 * @returns {string} The rendered HTML.
 */
export function renderMarkdown(
  content,
  { rules = {}, inline = false, disabledRules = [] } = {}
) {
  md.renderer.rules = { ...baseRules, ...rules }
  if (disabledRules.length > 0) {
    md.disable(disabledRules, true)
  }
  try {
    return inline ? md.renderInline(content) : md.render(content)
  } finally {
    // Leave the shared parser as the next call expects to find it.
    if (disabledRules.length > 0) {
      md.enable(disabledRules, true)
    }
    md.renderer.rules = { ...baseRules }
  }
}
