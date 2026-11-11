import { markdownToHtml } from '@baserow/modules/core/utils/markdownToHtml'

// Keep these vectors identical to the ones in
// backend/tests/baserow/core/test_core_markdown.py: both renderers must
// produce the same HTML for the same markdown.
const SHARED_VECTORS = [
  ['', ''],
  ['**bold** _italic_', '<p><strong>bold</strong> <em>italic</em></p>'],
  ['# Title\n\ntext', '<h1>Title</h1>\n<p>text</p>'],
  // Raw HTML is escaped.
  ['<b>x</b>', '<p>&lt;b&gt;x&lt;/b&gt;</p>'],
  // markdown-it refuses unsafe link destinations and renders them literally.
  ['[a](javascript:alert(1))', '<p>[a](javascript:alert(1))</p>'],
  [
    '[ok](https://e.com)',
    '<p><a href="https://e.com" rel="noopener noreferrer">ok</a></p>',
  ],
  ['~~s~~', '<p><s>s</s></p>'],
  // Non-standard editor marks stay literal, like in the grid preview.
  ['++u++ ~sub~', '<p>++u++ ~sub~</p>'],
  [
    '| a |\n|---|\n| b |',
    '<table>\n<thead>\n<tr>\n<th>a</th>\n</tr>\n</thead>\n' +
      '<tbody>\n<tr>\n<td>b</td>\n</tr>\n</tbody>\n</table>',
  ],
  // Soft line breaks are kept as is.
  ['line1\nline2', '<p>line1\nline2</p>'],
  [
    '- [ ] open\n- [x] done',
    '<ul class="contains-task-list">\n' +
      '<li class="task-list-item"><input class="task-list-item-checkbox" ' +
      'disabled="" type="checkbox"> open</li>\n' +
      '<li class="task-list-item"><input class="task-list-item-checkbox" ' +
      'checked="" disabled="" type="checkbox"> done</li>\n' +
      '</ul>',
  ],
  // A Baserow image reference in its API form keeps the resolved URL.
  [
    '![logo][abc_def.png](https://cdn/x.png)',
    '<p><img src="https://cdn/x.png" alt="logo"></p>',
  ],
  [
    '![ext](https://other/x.png)',
    '<p><img src="https://other/x.png" alt="ext"></p>',
  ],
  // Image references inside code are left untouched.
  [
    '`![logo][abc_def.png](https://cdn/x.png)`',
    '<p><code>![logo][abc_def.png](https://cdn/x.png)</code></p>',
  ],
  // Mentions are plain text: the stored form cannot be told apart from an
  // email address or a time, so they are never resolved to names.
  ['@42 hi', '<p>@42 hi</p>'],
  ['john@42.com and meet @9', '<p>john@42.com and meet @9</p>'],
]

describe('markdownToHtml', () => {
  test.each(SHARED_VECTORS)('renders %j', (content, expected) => {
    expect(markdownToHtml(content)).toBe(expected)
  })

  test('returns an empty string for a non-string value', () => {
    expect(markdownToHtml(null)).toBe('')
    expect(markdownToHtml(undefined)).toBe('')
    expect(markdownToHtml(42)).toBe('')
  })

  test('renders a bare image reference as its alt text', () => {
    // The browser cannot compute a storage URL from a file name; the backend
    // resolves one and renders an `<img>` instead.
    expect(markdownToHtml('![logo][abc_def.png] and `![x][abc_def.png]`')).toBe(
      '<p>logo and <code>![x][abc_def.png]</code></p>'
    )
  })

  test('keeps the alt text of a bare image reference literal', () => {
    // The editor escapes `[`, `]` and `\` in alt text and markdown-it unescapes
    // them, so the text cannot turn into a link.
    expect(markdownToHtml('![\\[a\\](https://e.com)][abc_def.png]')).toBe(
      '<p>[a](https://e.com)</p>'
    )
  })
})
