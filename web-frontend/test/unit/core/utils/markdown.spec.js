import { renderMarkdown } from '@baserow/modules/core/utils/markdown'

const abTextRules = {
  paragraph_open: (tokens, idx, options, env, renderer) => {
    tokens[idx].attrJoin('class', 'ab-text')
    return renderer.renderToken(tokens, idx, options)
  },
}

describe('renderMarkdown', () => {
  test('renders block markdown with a wrapping paragraph', () => {
    expect(renderMarkdown('**bold**')).toBe('<p><strong>bold</strong></p>\n')
  })

  test('renders inline markdown without a wrapping paragraph', () => {
    expect(renderMarkdown('**bold** _italic_', { inline: true })).toBe(
      '<strong>bold</strong> <em>italic</em>'
    )
  })

  test('escapes HTML', () => {
    expect(
      renderMarkdown('<img src=x onerror=alert(1)>', { inline: true })
    ).toBe('&lt;img src=x onerror=alert(1)&gt;')
  })

  test('applies the given renderer rules', () => {
    expect(renderMarkdown('Hello', { rules: abTextRules })).toBe(
      '<p class="ab-text">Hello</p>\n'
    )
  })

  test('restores the default rules for the next call', () => {
    renderMarkdown('Hello', { rules: abTextRules })

    expect(renderMarkdown('Hello')).toBe('<p>Hello</p>\n')
  })

  test('switches off the given rules', () => {
    const content =
      '![alt](https://example.com/a.png) [link](https://example.com)'

    const html = renderMarkdown(content, {
      inline: true,
      disabledRules: ['image', 'link'],
    })

    expect(html).not.toContain('<img')
    expect(html).not.toContain('<a ')
    expect(html).toBe(content)
  })

  test('switches the disabled rules back on for the next call', () => {
    const image = '![alt](https://example.com/a.png)'
    renderMarkdown(image, { inline: true, disabledRules: ['image'] })

    expect(renderMarkdown(image, { inline: true })).toBe(
      '<img src="https://example.com/a.png" alt="alt">'
    )
  })

  test('ignores unknown rule names', () => {
    expect(renderMarkdown('Hello', { disabledRules: ['does_not_exist'] })).toBe(
      '<p>Hello</p>\n'
    )
  })

  test('renders a hard line break unless the newline rule is off', () => {
    expect(renderMarkdown('a  \nb', { inline: true })).toBe('a<br>\nb')
    expect(
      renderMarkdown('a  \nb', { inline: true, disabledRules: ['newline'] })
    ).not.toContain('<br')
  })
})
