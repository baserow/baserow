import MarkdownIt from 'markdown-it'
import { createApplicationBuilderMarkdownRules } from '@baserow/modules/builder/utils/markdown'

const renderMarkdown = (
  content,
  { builder = { id: 1 }, mode = 'public' } = {}
) => {
  const markdown = new MarkdownIt()
  markdown.renderer.rules = {
    ...markdown.renderer.rules,
    ...createApplicationBuilderMarkdownRules({ builder, mode }),
  }
  return markdown.render(content)
}

describe('createApplicationBuilderMarkdownRules', () => {
  test.each([
    [
      'inline',
      '`</code><img src=x onerror=alert(document.domain)>`',
      '&lt;/code&gt;&lt;img src=x onerror=alert(document.domain)&gt;',
    ],
    [
      'fenced',
      '```\n</pre></code><img src=x onerror=alert(document.domain)>\n```',
      '&lt;/pre&gt;&lt;/code&gt;&lt;img src=x onerror=alert(document.domain)&gt;',
    ],
  ])('escapes HTML in %s code', (type, content, escapedContent) => {
    const html = renderMarkdown(content)

    expect(html).not.toContain('<img')
    expect(html).toContain(escapedContent)
  })

  test('renders HTML-looking content as inline code', () => {
    const html = renderMarkdown('`const template = "<div>hello</div>"`')

    expect(html).toContain(
      '<code class="ab-code ab-code--inline">' +
        'const template = &quot;&lt;div&gt;hello&lt;/div&gt;&quot;</code>'
    )
    expect(html).not.toContain('<div>hello</div>')
  })

  test('adds Application Builder classes', () => {
    const html = renderMarkdown(
      '# Heading\n\nParagraph\n\n> Quote\n\n- List item\n\n---'
    )

    expect(html).toContain('class="ab-heading ab-heading--h1"')
    expect(html).toContain('class="ab-text"')
    expect(html).toContain('class="ab-blockquote"')
    expect(html).toContain('class="ab-list"')
    expect(html).toContain('class="ab-list__item"')
    expect(html).toContain('class="ab-hr"')
  })

  test('prefixes internal links in preview mode', () => {
    const html = renderMarkdown('[Link](/path)', {
      builder: { id: 42 },
      mode: 'preview',
    })

    expect(html).toContain(
      '<a href="/builder/preview/42/path" class="ab-link">Link</a>'
    )
  })
})
