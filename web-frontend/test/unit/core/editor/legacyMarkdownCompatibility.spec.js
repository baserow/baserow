import { Editor } from '@tiptap/core'
import MarkdownIt from 'markdown-it'
import taskLists from 'markdown-it-task-lists'

import {
  createRichTextContentExtensions,
  createRichTextEditorExtensions,
} from '@baserow/modules/core/editor/richTextExtensions'
import {
  createMention,
  parseMention,
} from '@baserow/modules/core/editor/mention'

const USERS = [
  { user_id: 1, name: 'Jane Doe' },
  { user_id: 42, name: 'Ada Lovelace' },
]

const LEGACY_MARKDOWN_VALUES = [
  ['empty', ''],
  ['plain text', 'plain text'],
  ['unicode', 'Zażółć 🧑🏾‍💻 日本語 é'],
  ['windows newlines', 'first\r\nsecond\r\n\r\nthird'],
  ['old mac newlines', 'first\rsecond'],
  ['tabs', '\tindented\ntext\twith\ttabs'],
  ['leading and trailing whitespace', '  leading\ntrailing  '],
  ['soft breaks', 'first\nsecond\nthird'],
  ['hard breaks with spaces', 'first  \nsecond'],
  ['hard breaks with slash', 'first\\\nsecond'],
  ['many blank lines', '\n\nfirst\n\n\n\nsecond\n\n'],
  ['atx headings', '# one\n\n## two\n\n### three'],
  ['unsupported heading depths', '#### four\n\n##### five\n\n###### six'],
  ['setext headings', 'one\n===\n\ntwo\n---'],
  ['thematic breaks', 'before\n\n---\n\n***\n\nafter'],
  ['emphasis', '*one* _two_ **three** __four__ ***five***'],
  ['strikethrough', '~~deleted~~ and ~not deleted~'],
  ['unclosed emphasis', '**bold *italic _still open'],
  ['inline code', '`const value = 1` and ``a ` b``'],
  ['inline code whitespace and entities', '` trailing ` and `&#32;`'],
  ['escaped punctuation', '\\*literal\\* \\# heading \\[link\\]'],
  ['entities', '&lt;tag&gt; &amp; &#35; &#x1F600;'],
  ['inline link', '[Baserow](https://baserow.io "title")'],
  ['reference links', '[Baserow][site]\n\n[site]: https://baserow.io "title"'],
  ['collapsed reference link', '[Baserow][]\n\n[Baserow]: https://baserow.io'],
  ['shortcut reference link', '[Baserow]\n\n[Baserow]: https://baserow.io'],
  ['angle autolinks', '<https://baserow.io> <dev@baserow.io>'],
  ['bare link', 'https://baserow.io'],
  ['unsafe link', '[x](javascript:alert(1))'],
  ['image', 'before ![alt text](https://example.com/image.png "title") after'],
  [
    'reference image',
    '![alt][image]\n\n[image]: https://example.com/image.png',
  ],
  ['blockquote', '> first\n> second\n>\n> third'],
  ['nested blockquote', '> outer\n> > inner'],
  ['bullet markers', '- one\n* two\n+ three'],
  ['ordered list', '3. three\n4. four'],
  ['alternate ordered marker', '1) one\n2) two'],
  ['nested lists', '- one\n  1. nested\n  2. nested\n- two'],
  ['loose list', '- first paragraph\n\n  second paragraph\n\n- next item'],
  ['task list', '- [x] done\n- [ ] pending\n- [X] also done'],
  ['mixed task and bullet list', '- [x] done\n- plain\n- [ ] pending'],
  ['fenced code', '```js\nconst value = 1\n\nreturn value\n```'],
  ['tilde fenced code', '~~~python\nprint("hello")\n~~~'],
  ['longer nested fence', '````md\n```js\ncode\n```\n````'],
  ['unclosed fence', '```js\nconst value = 1'],
  ['indented code', '    const value = 1\n    return value'],
  ['raw html block', '<div><strong>literal</strong></div>'],
  ['raw script', '<script>alert("unsafe")</script>'],
  ['raw html with a mention', '<script>alert("unsafe")</script> @1'],
  ['html comment', 'before\n\n<!-- comment -->\n\nafter'],
  ['table', '| a | b |\n| --- | ---: |\n| one | two |'],
  ['definition without use', '[unused]: https://example.com'],
  ['known mention', 'Hello @1 and @42'],
  ['unknown mention', 'Hello @999999'],
  ['mention next to text', 'email@1.example @1suffix (@42),'],
  ['malformed links', '[text]( <url> "title" and ![alt](missing'],
  ['syntax only', '#\n\n>\n\n-\n\n1.'],
  ['only whitespace', ' \t \n\n \n'],
  ['zero width characters', 'a\u200Bb\u200Dc\uFEFFd'],
]

const createEditor = (content) => {
  const extensions = createRichTextEditorExtensions()
  extensions.push(createMention({ users: USERS }))
  return new Editor({ extensions, content, contentType: 'markdown' })
}

const reopen = (editor) => {
  const markdown = editor.getMarkdown()
  editor.destroy()
  return { editor: createEditor(markdown), markdown }
}

const parseWithLegacyMarkdown = (markdown) => {
  const parser = new MarkdownIt({ html: false, linkify: false, breaks: true })
  parser.use(taskLists)
  parser.use(parseMention(USERS))

  const container = document.createElement('div')
  container.innerHTML = parser.render(markdown)
  container.querySelectorAll('.contains-task-list').forEach((list) => {
    list.setAttribute('data-type', 'taskList')
  })
  container.querySelectorAll('.task-list-item').forEach((item) => {
    const input = item.querySelector('input')
    item.setAttribute('data-type', 'taskItem')
    item.setAttribute('data-checked', input?.checked ?? false)
    input?.remove()
  })
  container.querySelectorAll('pre > code').forEach((code) => {
    code.textContent = code.textContent.replace(/\n$/, '')
  })

  const extensions = createRichTextContentExtensions().filter(
    ({ name }) => name !== 'code'
  )
  extensions.push(createMention({ users: USERS }))
  const editor = new Editor({ extensions, content: container.innerHTML })
  const json = editor.getJSON()
  editor.destroy()
  return json
}

describe('legacy database Markdown compatibility', () => {
  test('always produces a valid ProseMirror document', () => {
    const invalidDocuments = []

    for (const [name, markdown] of LEGACY_MARKDOWN_VALUES) {
      const editor = createEditor(markdown)
      try {
        editor.state.doc.check()
      } catch (error) {
        invalidDocuments.push({
          name,
          message: error.message,
          json: editor.getJSON(),
        })
      }
      editor.destroy()
    }

    expect(invalidDocuments).toStrictEqual([])
  })

  test('preserves document semantics after saving and reopening', () => {
    const unstableValues = []

    for (const [name, markdown] of LEGACY_MARKDOWN_VALUES) {
      let editor = createEditor(markdown)
      const parsed = editor.getJSON()
      const reopened = reopen(editor)
      editor = reopened.editor

      try {
        editor.state.doc.check()
        if (JSON.stringify(editor.getJSON()) !== JSON.stringify(parsed)) {
          unstableValues.push({
            name,
            savedMarkdown: reopened.markdown,
            parsed,
            reopened: editor.getJSON(),
          })
        }
      } finally {
        editor.destroy()
      }
    }

    expect(unstableValues).toStrictEqual([])
  })

  test('matches the legacy parser unless the new behavior preserves more data', () => {
    const intentionalImprovements = new Set([
      'tabs',
      'leading and trailing whitespace',
      'many blank lines',
      'inline code',
      'inline code whitespace and entities',
      'image',
      'reference image',
      'mixed task and bullet list',
      'table',
      'definition without use',
    ])
    const regressions = []

    for (const [name, markdown] of LEGACY_MARKDOWN_VALUES) {
      if (intentionalImprovements.has(name)) {
        continue
      }
      const editor = createEditor(markdown)
      const actual = editor.getJSON()
      const legacy = parseWithLegacyMarkdown(markdown)
      editor.destroy()

      if (JSON.stringify(actual) !== JSON.stringify(legacy)) {
        regressions.push({ name, legacy, actual })
      }
    }

    expect(regressions).toStrictEqual([])
  })

  test('retains content in legacy edge cases', () => {
    const cases = [
      ['inline code', '`code`', 'code'],
      [
        'raw HTML',
        '<script>alert("unsafe")</script>',
        '<script>alert("unsafe")</script>',
      ],
      ['numeric entities', '&#35; &#x1F600;', '# 😀'],
      ['unsafe links', '[x](javascript:alert(1))', '[x](javascript:alert(1))'],
      [
        'unused definitions',
        '[unused]: https://example.com',
        '[unused]: https://example.com',
      ],
    ]

    for (const [name, markdown, text] of cases) {
      const editor = createEditor(markdown)
      expect({ name, text: editor.getText() }).toStrictEqual({ name, text })
      editor.destroy()
    }
  })

  test('handles generated malformed and mixed Markdown values', () => {
    const fragments = [
      'plain',
      '**bold',
      '_italic_',
      '`code`',
      '[link](https://baserow.io)',
      '[broken](',
      '<script>x</script>',
      '&#35;',
      '@1',
      '@999999',
      '- [x] task',
      '> quote',
      '```js\ncode\n```',
      '\\*escaped\\*',
      '🧑🏾‍💻',
      '\u200B',
    ]
    const separators = ['', ' ', '\n', '\n\n', '\r\n', '\t']
    let state = 0x2495
    const random = (length) => {
      state = (state * 1664525 + 1013904223) >>> 0
      return state % length
    }

    for (let valueIndex = 0; valueIndex < 100; valueIndex++) {
      let markdown = ''
      const fragmentCount = 1 + random(12)
      for (let index = 0; index < fragmentCount; index++) {
        markdown += fragments[random(fragments.length)]
        markdown += separators[random(separators.length)]
      }

      let editor = createEditor(markdown)
      const parsed = editor.getJSON()
      expect(() => editor.state.doc.check()).not.toThrow()
      editor = reopen(editor).editor
      expect({
        valueIndex,
        markdown,
        document: editor.getJSON(),
      }).toStrictEqual({ valueIndex, markdown, document: parsed })
      expect(() => editor.state.doc.check()).not.toThrow()
      editor.destroy()
    }
  })

  test('loads and saves a value at the default database length limit', () => {
    const markdown = 'a'.repeat(1_000_000)
    const editor = createEditor('')

    const parsed = editor.markdown.parse(markdown)
    const document = editor.schema.nodeFromJSON(parsed)
    document.check()
    const serialized = editor.markdown.serialize(parsed)
    expect(serialized).toBe(markdown)
    expect(editor.markdown.parse(serialized)).toStrictEqual(parsed)
    editor.destroy()
  })
})
