import { Editor } from '@tiptap/core'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import { Markdown as TiptapMarkdown } from 'tiptap-markdown'
import Markdown from 'markdown-it'
import {
  blankLinePreservation,
  padBlankLinesForMarkdown,
  ParagraphWithEmptyPreservation,
} from '@baserow/modules/core/editor/emptyParagraphPreservation'

function render(text) {
  const md = new Markdown()
  md.use(blankLinePreservation)
  return md.render(text)
}

function countEmptyParagraphs(html) {
  return (html.match(/<p><\/p>/g) || []).length
}

describe('blankLinePreservation', () => {
  it('does not add empty paragraphs for standard paragraph breaks', () => {
    const html = render('hello\n\nworld')
    expect(countEmptyParagraphs(html)).toBe(0)
    expect(html).toContain('<p>hello</p>')
    expect(html).toContain('<p>world</p>')
  })

  it('preserves one blank line as one empty paragraph', () => {
    const html = render('hello\n\n\nworld')
    expect(countEmptyParagraphs(html)).toBe(1)
  })

  it('preserves two blank lines as two empty paragraphs', () => {
    const html = render('hello\n\n\n\nworld')
    expect(countEmptyParagraphs(html)).toBe(2)
  })

  it('preserves three blank lines as three empty paragraphs', () => {
    const html = render('hello\n\n\n\n\nworld')
    expect(countEmptyParagraphs(html)).toBe(3)
  })

  it('handles blank lines between heading and paragraph', () => {
    const html = render('# Title\n\n\nContent')
    expect(countEmptyParagraphs(html)).toBe(1)
  })

  it('does not add empty paragraphs for single newlines', () => {
    const html = render('hello\nworld')
    expect(countEmptyParagraphs(html)).toBe(0)
  })

  it('handles empty input', () => {
    const html = render('')
    expect(countEmptyParagraphs(html)).toBe(0)
  })

  it('handles multiple sections with different spacing', () => {
    const html = render('A\n\nB\n\n\nC\n\n\n\nD')
    // A→B: standard break (0), B→C: 1 blank line (1), C→D: 2 blank lines (2)
    expect(countEmptyParagraphs(html)).toBe(3)
  })

  it('is idempotent when registered multiple times', () => {
    const md = new Markdown()
    md.use(blankLinePreservation)
    md.use(blankLinePreservation)
    md.use(blankLinePreservation)
    const html = md.render('hello\n\n\nworld')
    expect(countEmptyParagraphs(html)).toBe(1)
  })
})

describe('padBlankLinesForMarkdown', () => {
  it('adds one newline to runs of 2+ newlines', () => {
    expect(padBlankLinesForMarkdown('a\n\nb')).toBe('a\n\n\nb')
    expect(padBlankLinesForMarkdown('a\n\n\nb')).toBe('a\n\n\n\nb')
  })

  it('does not modify single newlines', () => {
    expect(padBlankLinesForMarkdown('a\nb')).toBe('a\nb')
  })

  it('does not modify text without newlines', () => {
    expect(padBlankLinesForMarkdown('hello')).toBe('hello')
  })
})

describe('ParagraphWithEmptyPreservation round-trip', () => {
  let editor

  function createEditor(markdown) {
    return new Editor({
      extensions: [
        Document,
        ParagraphWithEmptyPreservation,
        Text,
        TiptapMarkdown.configure({ html: false, breaks: true }),
      ],
      content: markdown,
    })
  }

  function roundTrip(markdown) {
    editor = createEditor(markdown)
    return editor.storage.markdown.getMarkdown().trim()
  }

  afterEach(() => {
    editor?.destroy()
  })

  it('preserves standard paragraph break', () => {
    expect(roundTrip('hello\n\nworld')).toBe('hello\n\nworld')
  })

  it('preserves one extra blank line', () => {
    expect(roundTrip('hello\n\n\nworld')).toBe('hello\n\n\nworld')
  })

  it('preserves multiple extra blank lines', () => {
    expect(roundTrip('hello\n\n\n\nworld')).toBe('hello\n\n\n\nworld')
  })

  it('preserves mixed spacing across sections', () => {
    expect(roundTrip('A\n\nB\n\n\nC\n\n\n\nD')).toBe('A\n\nB\n\n\nC\n\n\n\nD')
  })
})
