import { Editor, Node } from '@tiptap/core'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import { Paragraph } from '@tiptap/extension-paragraph'
import { FunctionDowngradeExtension } from '@baserow/modules/core/components/formula/extensions/FunctionDowngradeExtension'

const FunctionFormulaComponent = Node.create({
  name: 'function-formula-component',
  group: 'inline',
  inline: true,
  atom: true,
  addAttributes() {
    return { functionName: { default: null }, hasNoArgs: { default: false } }
  },
  renderHTML() {
    return ['span', { 'data-type': 'function-formula-component' }]
  },
})

const FunctionClosingParen = Node.create({
  name: 'function-closing-paren',
  group: 'inline',
  inline: true,
  atom: true,
  addAttributes() {
    return { noArgs: { default: false } }
  },
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
      FunctionDowngradeExtension,
    ],
    content,
  })
}

/**
 * Deletes every `function-closing-paren` node currently in the doc by
 * dispatching a single transaction. Done in reverse document order so
 * earlier positions stay stable. Mirrors what SmartDeletionExtension
 * does when the user presses Backspace right after a `)`.
 */
function deleteAllClosers(editor) {
  const positions = []
  editor.state.doc.descendants((node, pos) => {
    if (node.type.name === 'function-closing-paren') {
      positions.push({ pos, size: node.nodeSize })
    }
  })
  positions.sort((a, b) => b.pos - a.pos)
  const tr = editor.state.tr
  for (const { pos, size } of positions) {
    tr.delete(pos, pos + size)
  }
  editor.view.dispatch(tr)
}

/**
 * Serialises the paragraph contents into a compact string representation:
 *   - `FN{name}` for function-formula-component
 *   - `)` for function-closing-paren
 *   - `GROUP(` / `GROUP)` for group parens
 *   - raw text for text nodes (with ZWS as `Z`)
 */
function serialise(editor) {
  const parts = []
  editor.state.doc.descendants((node) => {
    const name = node.type.name
    if (name === 'function-formula-component') {
      parts.push(`FN{${node.attrs.functionName}}`)
    } else if (name === 'function-closing-paren') {
      parts.push(')')
    } else if (name === 'group-opening-paren') {
      parts.push('GROUP(')
    } else if (name === 'group-closing-paren') {
      parts.push('GROUP)')
    } else if (node.isText) {
      parts.push(node.text.replace(/\u200B/g, 'Z'))
    }
  })
  return parts.join('|')
}

describe('FunctionDowngradeExtension', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  it('downgrades a function opener to plain text when its closer is removed', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: '\u200B' },
            {
              type: 'function-formula-component',
              attrs: { functionName: 'today', hasNoArgs: true },
            },
            { type: 'text', text: '\u200B' },
            { type: 'function-closing-paren', attrs: { noArgs: true } },
            { type: 'text', text: '\u200B' },
          ],
        },
      ],
    })

    deleteAllClosers(editor)

    expect(serialise(editor)).not.toContain('FN{today}')
    // Plain text `today(` remains (ZWS markers around the atom are
    // stripped and surrounding ZWS text nodes merge).
    expect(editor.state.doc.textContent.replace(/\u200B/g, '')).toBe('today(')
  })

  it('leaves a properly closed function untouched on unrelated doc changes', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: '\u200B' },
            {
              type: 'function-formula-component',
              attrs: { functionName: 'today', hasNoArgs: true },
            },
            { type: 'function-closing-paren', attrs: { noArgs: true } },
            { type: 'text', text: '\u200B' },
          ],
        },
      ],
    })

    // Dispatch a real doc-changing transaction that doesn't touch the
    // function pair.
    editor.view.dispatch(editor.state.tr.insertText('x', 1))

    expect(serialise(editor)).toContain('FN{today}')
    expect(serialise(editor)).toContain(')')
  })

  it('downgrades outer unmatched function while keeping inner balanced one', () => {
    // `year(today())` — we remove only the outer closer.
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
            {
              type: 'function-formula-component',
              attrs: { functionName: 'today', hasNoArgs: true },
            },
            { type: 'function-closing-paren', attrs: { noArgs: true } }, // inner
            { type: 'function-closing-paren', attrs: { noArgs: false } }, // outer
          ],
        },
      ],
    })

    // Remove only the outermost (= last) closing paren.
    let lastPos = -1
    let lastSize = 0
    editor.state.doc.descendants((node, pos) => {
      if (node.type.name === 'function-closing-paren') {
        lastPos = pos
        lastSize = node.nodeSize
      }
    })
    editor.view.dispatch(editor.state.tr.delete(lastPos, lastPos + lastSize))

    const out = serialise(editor)
    expect(out).not.toContain('FN{year}')
    expect(out).toContain('FN{today}')
    // Exactly one closer (the inner one) must remain.
    expect((out.match(/\)/g) || []).length).toBe(1)
  })

  it('downgrades both functions when both become unmatched', () => {
    // `year(today())` — we remove both closers at once.
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
            {
              type: 'function-formula-component',
              attrs: { functionName: 'today', hasNoArgs: true },
            },
            { type: 'function-closing-paren', attrs: { noArgs: true } },
            { type: 'function-closing-paren', attrs: { noArgs: false } },
          ],
        },
      ],
    })

    deleteAllClosers(editor)

    const out = serialise(editor)
    expect(out).not.toContain('FN{year}')
    expect(out).not.toContain('FN{today}')
    expect(editor.state.doc.textContent.replace(/\u200B/g, '')).toBe(
      'year(today('
    )
  })

  it('strips ZWS markers around the downgraded function atom', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            { type: 'text', text: '\u200B' },
            {
              type: 'function-formula-component',
              attrs: { functionName: 'month', hasNoArgs: false },
            },
            { type: 'text', text: '\u200B' },
            { type: 'function-closing-paren' },
            { type: 'text', text: '\u200B' },
          ],
        },
      ],
    })

    deleteAllClosers(editor)

    // Without the ZWS stripping, the resulting text would contain
    // stray ZWS characters inside the `month(` text. We want it clean.
    expect(editor.state.doc.textContent).toBe('month(')
  })

  it('downgrades the inner function when its own closer is removed (nested)', () => {
    // `concat(if(...),"lorem ipsum")` — we remove the INNER closer (the one
    // that was paired with `if(`). The outer `concat(...)` stays fully
    // balanced because its own closer is untouched, so it must remain
    // highlighted while `if(` becomes plain text.
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [
            {
              type: 'function-formula-component',
              attrs: { functionName: 'concat', hasNoArgs: false },
            },
            {
              type: 'function-formula-component',
              attrs: { functionName: 'if', hasNoArgs: false },
            },
            { type: 'text', text: '5>2,"yes","no"' },
            { type: 'function-closing-paren' }, // inner (if)
            { type: 'text', text: ',"lorem ipsum"' },
            { type: 'function-closing-paren' }, // outer (concat)
          ],
        },
      ],
    })

    // Remove only the first function-closing-paren (inner, matches `if`).
    let innerClosePos = -1
    let innerCloseSize = 0
    editor.state.doc.descendants((node, pos) => {
      if (innerClosePos === -1 && node.type.name === 'function-closing-paren') {
        innerClosePos = pos
        innerCloseSize = node.nodeSize
      }
    })
    editor.view.dispatch(
      editor.state.tr.delete(innerClosePos, innerClosePos + innerCloseSize)
    )

    const out = serialise(editor)
    // concat must stay highlighted (its own closer is still there).
    expect(out).toContain('FN{concat}')
    // if must be downgraded to plain text.
    expect(out).not.toContain('FN{if}')
    expect(out).toMatch(/if\(/)
    // Exactly one closer remains — the one paired with concat.
    expect((out.match(/\)/g) || []).length).toBe(1)
  })

  it('preserves a dangling group-opening-paren (not a function concern)', () => {
    // The extension is function-specific: a bare unclosed group
    // (legitimately produced by the tolerant parser on pastes like
    // `(hello`) must be preserved.
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

    editor.view.dispatch(editor.state.tr.insertText('y', 3))

    expect(serialise(editor)).toContain('GROUP(')
  })
})
