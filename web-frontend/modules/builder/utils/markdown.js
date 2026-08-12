import { escapeHtml } from '@baserow/modules/core/utils/string'
import { prefixInternalResolvedUrl } from '@baserow/modules/builder/utils/urlResolution'

/**
 * Creates the Markdown-It renderer rules used by Application Builder content.
 * These rules add the Application Builder CSS classes and safely render token
 * content interpolated into HTML.
 */
export const createApplicationBuilderMarkdownRules = ({ mode, builderId }) => ({
  heading_open: (tokens, idx, options, env, renderer) => {
    const level = tokens[idx].markup.length
    tokens[idx].attrJoin('class', `ab-heading ab-heading--h${level}`)
    return renderer.renderToken(tokens, idx, options)
  },
  link_open: (tokens, idx, options, env, renderer) => {
    const url = prefixInternalResolvedUrl(
      tokens[idx].attrGet('href'),
      'custom',
      mode,
      builderId
    )
    tokens[idx].attrSet('href', url)
    tokens[idx].attrJoin('class', 'ab-link')
    return renderer.renderToken(tokens, idx, options)
  },
  image: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-image')
    return renderer.renderToken(tokens, idx, options)
  },
  paragraph_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-text')
    return renderer.renderToken(tokens, idx, options)
  },
  blockquote_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-blockquote')
    return renderer.renderToken(tokens, idx, options)
  },
  fence: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-code')

    return `${renderer.renderToken(tokens, idx, options)}<pre>${escapeHtml(
      tokens[idx].content
    )}</pre></code>`
  },
  code_inline: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-code ab-code--inline')
    return `${renderer.renderToken(tokens, idx, options)}${escapeHtml(
      tokens[idx].content
    )}</code>`
  },
  hr: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-hr')
    return renderer.renderToken(tokens, idx, options)
  },
  table_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'baserow-table baserow-table--horizontal')
    return `<div class="ab-table">${renderer.renderToken(tokens, idx, options)}`
  },
  table_close: (tokens, idx, options, env, renderer) => {
    return `${renderer.renderToken(tokens, idx, options)}</div>`
  },
  tr_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'baserow-table__row')
    return renderer.renderToken(tokens, idx, options)
  },
  th_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-table__header-cell')
    return `${renderer.renderToken(tokens, idx, options)}<div>`
  },
  td_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-table__cell')
    return `${renderer.renderToken(
      tokens,
      idx,
      options
    )}<div class="ab-table__cell-content">`
  },
  td_close: (tokens, idx, options, env, renderer) => {
    return `</div>${renderer.renderToken(tokens, idx, options)}`
  },
  ordered_list_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-list')
    return renderer.renderToken(tokens, idx, options)
  },
  list_item_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-list__item')
    return renderer.renderToken(tokens, idx, options)
  },
  bullet_list_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-list')
    return renderer.renderToken(tokens, idx, options)
  },
})

/**
 * The rendering presets available for Application Builder Markdown surfaces.
 *
 * - `block`: the full Markdown syntax, for free-flowing text (Text element, Text
 *   collection field, file input help text).
 * - `restrictedBlock`: block mode without the layout-breaking blocks (tables,
 *   code blocks, images, headings), for the notification toast description.
 * - `inline`: emphasis, strikethrough and inline code only, for selectable or
 *   truncated single-line content (option names, table headers, toast title).
 *   Links are disabled, as these contexts are either already wrapped in
 *   an `<a>`, or select something on click.
 * - `inlineLinks`: inline mode with links, for descriptive single-line content
 *   such as form field labels ("I agree to the [terms](...)").
 */
export const MARKDOWN_PRESETS = {
  BLOCK: 'block',
  RESTRICTED_BLOCK: 'restrictedBlock',
  INLINE: 'inline',
  INLINE_LINKS: 'inlineLinks',
}

export const INLINE_MARKDOWN_DISABLED_RULES = ['link', 'autolink']
export const INLINE_LINKS_MARKDOWN_DISABLED_RULES = []
export const RESTRICTED_BLOCK_MARKDOWN_DISABLED_RULES = [
  'table',
  'fence',
  'code',
  'heading',
  'lheading',
]

/**
 * Renders an image token back as its Markdown source. Disabling the `image`
 * rule instead would leave a `!` followed by a link, which is more surprising
 * than the literal text on the surfaces where images aren't allowed.
 */
const renderImageAsSource = (tokens, idx) => {
  const token = tokens[idx]
  const title = token.attrGet('title')
  return escapeHtml(
    `![${token.content}](${token.attrGet('src')}${title ? ` "${title}"` : ''})`
  )
}

/**
 * Creates the Markdown-It renderer rules used by the inline presets. Only the
 * tokens that survive `renderInline` need styling.
 */
export const createApplicationBuilderInlineMarkdownRules = ({
  builder,
  mode,
  links = false,
}) => {
  const blockRules = createApplicationBuilderMarkdownRules({ builder, mode })
  return {
    code_inline: blockRules.code_inline,
    image: renderImageAsSource,
    // Inline surfaces are often nowrap/ellipsis contexts where a `<br>` breaks
    // the truncation. A backslash-newline still yields a hardbreak even with the
    // `newline` rule disabled, so both break renderers emit a plain space.
    hardbreak: () => ' ',
    softbreak: () => ' ',
    ...(links ? { link_open: blockRules.link_open } : {}),
  }
}

/**
 * Returns the `MarkdownIt` component props (`inline`, `rules`, `disabledRules`)
 * for the given preset.
 */
export const createApplicationBuilderMarkdownPreset = (
  preset,
  { builder, mode }
) => {
  switch (preset) {
    case MARKDOWN_PRESETS.INLINE:
      return {
        inline: true,
        rules: createApplicationBuilderInlineMarkdownRules({ builder, mode }),
        disabledRules: INLINE_MARKDOWN_DISABLED_RULES,
      }
    case MARKDOWN_PRESETS.INLINE_LINKS:
      return {
        inline: true,
        rules: createApplicationBuilderInlineMarkdownRules({
          builder,
          mode,
          links: true,
        }),
        disabledRules: INLINE_LINKS_MARKDOWN_DISABLED_RULES,
      }
    case MARKDOWN_PRESETS.RESTRICTED_BLOCK:
      return {
        inline: false,
        rules: {
          ...createApplicationBuilderMarkdownRules({ builder, mode }),
          image: renderImageAsSource,
        },
        disabledRules: RESTRICTED_BLOCK_MARKDOWN_DISABLED_RULES,
      }
    case MARKDOWN_PRESETS.BLOCK:
      return {
        inline: false,
        rules: createApplicationBuilderMarkdownRules({ builder, mode }),
        disabledRules: [],
      }
    default:
      throw new Error(`Unknown markdown preset: ${preset}`)
  }
}

/**
 * Click handler for rendered Markdown: blocks navigation while editing and keeps
 * internal links inside the SPA router.
 */
export const handleMarkdownClick = (event, { mode, router }) => {
  if (mode === 'editing') {
    event.preventDefault()
    return
  }
  // The click target can be nested markup inside the link, e.g. the `<strong>`
  // of `[**terms**](/terms)`, so look up the closest link instead.
  const link = event.target.closest('a.ab-link')
  if (link) {
    const url = link.getAttribute('href')

    if (url.startsWith('/')) {
      event.preventDefault()
      router.push(url)
    }
  }
}
