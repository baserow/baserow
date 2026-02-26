import { Editor } from '@tiptap/core'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import { Paragraph } from '@tiptap/extension-paragraph'
import { Node } from '@tiptap/core'
import {
  ZWS,
  isZWSNode,
  zwsTextJSON,
  zwsTextNode,
  getTextBeforeCursor,
  findNextNonZWSNode,
  buildParenStack,
} from '@baserow/modules/core/components/formula/extensions/helpers'

const FunctionFormulaComponent = Node.create({
  name: 'function-formula-component',
  group: 'inline',
  inline: true,
  atom: true,
  addAttributes() {
    return { functionName: { default: null }, hasNoArgs: { default: false } }
  },
  renderHTML() {
    return ['span', { 'data-type': 'function-formula-component' }, 'fn(']
  },
})

const FunctionClosingParen = Node.create({
  name: 'function-closing-paren',
  group: 'inline',
  inline: true,
  atom: true,
  renderHTML() {
    return ['span', ')']
  },
})

const GroupOpeningParen = Node.create({
  name: 'group-opening-paren',
  group: 'inline',
  inline: true,
  atom: true,
  renderHTML() {
    return ['span', '(']
  },
})

const GroupClosingParen = Node.create({
  name: 'group-closing-paren',
  group: 'inline',
  inline: true,
  atom: true,
  renderHTML() {
    return ['span', ')']
  },
})

function createEditor(content) {
  return new Editor({
    extensions: [
      Document,
      Paragraph,
      Text,
      FunctionFormulaComponent,
      FunctionClosingParen,
      GroupOpeningParen,
      GroupClosingParen,
    ],
    content,
  })
}

// ── ZWS helpers ────────────────────────────────────────────────────

describe('ZWS constants and helpers', () => {
  describe('isZWSNode', () => {
    it('returns true for a single ZWS text node', () => {
      const node = { isText: true, text: '\u200B' }
      expect(isZWSNode(node)).toBe(true)
    })

    it('returns true for multiple consecutive ZWS', () => {
      const node = { isText: true, text: '\u200B\u200B\u200B' }
      expect(isZWSNode(node)).toBe(true)
    })

    it('returns false for regular text', () => {
      const node = { isText: true, text: 'hello' }
      expect(isZWSNode(node)).toBe(false)
    })

    it('returns false for text containing ZWS mixed with other chars', () => {
      const node = { isText: true, text: '\u200Bx' }
      expect(isZWSNode(node)).toBe(false)
    })

    it('returns false for non-text nodes', () => {
      const node = { isText: false, text: '\u200B' }
      expect(isZWSNode(node)).toBe(false)
    })

    it('returns falsy for null/undefined', () => {
      expect(isZWSNode(null)).toBeFalsy()
      expect(isZWSNode(undefined)).toBeFalsy()
    })

    it('returns falsy for empty text', () => {
      const node = { isText: true, text: '' }
      expect(isZWSNode(node)).toBeFalsy()
    })
  })

  describe('zwsTextJSON', () => {
    it('returns a text node JSON with ZWS content', () => {
      const result = zwsTextJSON()
      expect(result).toEqual({ type: 'text', text: ZWS })
    })

    it('returns a new object each call', () => {
      const a = zwsTextJSON()
      const b = zwsTextJSON()
      expect(a).not.toBe(b)
      expect(a).toEqual(b)
    })
  })

  describe('zwsTextNode', () => {
    let editor

    afterEach(() => {
      editor?.destroy()
    })

    it('creates a ProseMirror text node containing ZWS', () => {
      editor = createEditor('<p>test</p>')
      const node = zwsTextNode(editor.schema)
      expect(node.isText).toBe(true)
      expect(node.text).toBe(ZWS)
    })
  })
})

// ── getTextBeforeCursor ────────────────────────────────────────────

describe('getTextBeforeCursor', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  it('returns text before cursor in the middle of a text node', () => {
    editor = createEditor('<p>hello world</p>')
    const { doc } = editor.state
    // Position 6 = after "hello" (pos 1=h, 2=e, 3=l, 4=l, 5=o, 6= )
    const result = getTextBeforeCursor(doc, 6)
    expect(result).toBe('hello')
  })

  it('returns full text when cursor is at end of text node', () => {
    editor = createEditor('<p>abc</p>')
    const { doc } = editor.state
    // pos 1=a, 2=b, 3=c, 4=after c
    const result = getTextBeforeCursor(doc, 4)
    expect(result).toBe('abc')
  })

  it('returns empty string when cursor is at start of paragraph', () => {
    editor = createEditor('<p>abc</p>')
    const { doc } = editor.state
    const result = getTextBeforeCursor(doc, 1)
    expect(result).toBe('')
  })

  it('returns text before cursor when after an atom node followed by text', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            {
              type: 'function-formula-component',
              attrs: { functionName: 'today', hasNoArgs: true },
            },
            { type: 'text', text: 'abc' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    // pos: 1=atom(1), 2=a, 3=b, 4=c
    const result = getTextBeforeCursor(doc, 4)
    expect(result).toBe('ab')
  })
})

// ── findNextNonZWSNode ─────────────────────────────────────────────

describe('findNextNonZWSNode', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  it('skips ZWS and returns the next atom node', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: 'x' },
            { type: 'text', text: '\u200B' },
            { type: 'function-closing-paren' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    // pos 1=x, 2=ZWS, 3=closing-paren
    const result = findNextNonZWSNode(doc, 2)
    expect(result).not.toBeNull()
    expect(result.node.type.name).toBe('function-closing-paren')
    expect(result.pos).toBe(3)
  })

  it('skips multiple ZWS text nodes', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: 'x' },
            { type: 'text', text: '\u200B' },
            { type: 'text', text: '\u200B' },
            { type: 'group-closing-paren' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    const result = findNextNonZWSNode(doc, 2)
    expect(result).not.toBeNull()
    expect(result.node.type.name).toBe('group-closing-paren')
  })

  it('returns null when there is no next node', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: 'x' },
            { type: 'text', text: '\u200B' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    const result = findNextNonZWSNode(doc, 2)
    expect(result).toBeNull()
  })

  it('returns null when cursor is inside a non-ZWS text node', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [{ type: 'text', text: 'hello' }],
        },
      ],
    })
    const { doc } = editor.state
    const result = findNextNonZWSNode(doc, 3)
    expect(result).toBeNull()
  })

  it('returns the next node when there is no ZWS to skip', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'group-opening-paren' },
            { type: 'function-closing-paren' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    // After first atom (pos 2), next should be function-closing-paren
    const result = findNextNonZWSNode(doc, 2)
    expect(result).not.toBeNull()
    expect(result.node.type.name).toBe('function-closing-paren')
  })
})

// ── buildParenStack ────────────────────────────────────────────────

describe('buildParenStack', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  it('returns empty stack for text without parentheses', () => {
    editor = createEditor('<p>hello</p>')
    const { doc } = editor.state
    const stack = buildParenStack(doc, 1, 6)
    expect(stack).toEqual([])
  })

  it('tracks a function component as function paren', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            {
              type: 'function-formula-component',
              attrs: { functionName: 'year', hasNoArgs: false },
            },
            { type: 'text', text: 'arg' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    // wrapperStart=1, scan up to after 'arg'
    const stack = buildParenStack(doc, 1, 5)
    expect(stack).toEqual(['function'])
  })

  it('tracks a group-opening-paren as group paren', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'group-opening-paren' },
            { type: 'text', text: 'x' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    const stack = buildParenStack(doc, 1, 3)
    expect(stack).toEqual(['group'])
  })

  it('pops stack on function-closing-paren', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            {
              type: 'function-formula-component',
              attrs: { functionName: 'today', hasNoArgs: true },
            },
            { type: 'function-closing-paren' },
            { type: 'text', text: 'x' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    const stack = buildParenStack(doc, 1, 4)
    expect(stack).toEqual([])
  })

  it('pops stack on group-closing-paren', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'group-opening-paren' },
            { type: 'text', text: '1' },
            { type: 'group-closing-paren' },
            { type: 'text', text: 'x' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    const stack = buildParenStack(doc, 1, 5)
    expect(stack).toEqual([])
  })

  it('handles nested function inside group', () => {
    // (year(...) ...)
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'group-opening-paren' },
            {
              type: 'function-formula-component',
              attrs: { functionName: 'year', hasNoArgs: false },
            },
            { type: 'text', text: 'arg' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    const stack = buildParenStack(doc, 1, 6)
    expect(stack).toEqual(['group', 'function'])
  })

  it('handles nested function closed inside group', () => {
    // (year(arg) ...)
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'group-opening-paren' },
            {
              type: 'function-formula-component',
              attrs: { functionName: 'year', hasNoArgs: false },
            },
            { type: 'text', text: 'arg' },
            { type: 'function-closing-paren' },
            { type: 'text', text: 'x' },
          ],
        },
      ],
    })
    const { doc } = editor.state
    // After closing paren + 'x', only group is open
    const stack = buildParenStack(doc, 1, 7)
    expect(stack).toEqual(['group'])
  })

  it('tracks plain text parentheses as group', () => {
    editor = createEditor('<p>(hello</p>')
    const { doc } = editor.state
    const stack = buildParenStack(doc, 1, 7)
    expect(stack).toEqual(['group'])
  })

  it('pops plain text closing parentheses', () => {
    editor = createEditor('<p>(hello)</p>')
    const { doc } = editor.state
    const stack = buildParenStack(doc, 1, 8)
    expect(stack).toEqual([])
  })
})
