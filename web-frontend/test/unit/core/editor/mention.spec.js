import { parseMarkdown } from '@baserow/modules/core/editor/markdown'

describe('rich-text mention rendering', () => {
  const XSS_PAYLOAD = '"><img src=x onerror=alert(document.domain)>'

  test('escapes a malicious workspace user name (stored XSS)', () => {
    const users = [{ user_id: 1, name: XSS_PAYLOAD }]

    const html = parseMarkdown('Hello @1', { workspaceUsers: users })

    // The payload must not survive as a live element, nor break out of the
    // data-label attribute into the span's content.
    expect(html).not.toContain('<img')
    expect(html).not.toContain('data-label=""')
    expect(html).toContain('&lt;img')

    // Parsing the output confirms no injected element ever materializes; the
    // payload stays inert text inside the single mention span.
    const doc = new DOMParser().parseFromString(html, 'text/html')
    expect(doc.querySelector('img')).toBeNull()
    const mention = doc.querySelector('span[data-type="mention"]')
    expect(mention).not.toBeNull()
    expect(mention.getAttribute('data-id')).toBe('1')
    expect(mention.textContent).toBe(`@${XSS_PAYLOAD}`)
  })

  test('renders a normal workspace user name unchanged', () => {
    const users = [{ user_id: 1, name: 'Jane Doe' }]

    const html = parseMarkdown('Hello @1', { workspaceUsers: users })

    expect(html).toContain('data-label="Jane Doe"')
    expect(html).toContain('>@Jane Doe</span>')
    expect(html).toContain('data-type="mention"')
  })

  test('preserves ampersands in names without double-escaping the markup', () => {
    const users = [{ user_id: 2, name: 'Tom & Jerry' }]

    const html = parseMarkdown('Ping @2', { workspaceUsers: users })

    expect(html).toContain('Tom &amp; Jerry')
    expect(html).not.toContain('Tom & Jerry')
  })
})
