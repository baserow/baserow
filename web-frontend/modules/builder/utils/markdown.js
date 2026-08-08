import { escapeHtml } from '@baserow/modules/core/utils/string'
import { prefixInternalResolvedUrl } from '@baserow/modules/builder/utils/urlResolution'

/**
 * Creates the Markdown-It renderer rules used by Application Builder content.
 * These rules add the Application Builder CSS classes and safely render token
 * content interpolated into HTML.
 */
export const createApplicationBuilderMarkdownRules = ({ builder, mode }) => ({
  heading_open: (tokens, idx, options, env, renderer) => {
    const level = tokens[idx].markup.length
    tokens[idx].attrJoin('class', `ab-heading ab-heading--h${level}`)
    return renderer.renderToken(tokens, idx, options)
  },
  link_open: (tokens, idx, options, env, renderer) => {
    const url = prefixInternalResolvedUrl(
      tokens[idx].attrGet('href'),
      builder,
      'custom',
      mode
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
