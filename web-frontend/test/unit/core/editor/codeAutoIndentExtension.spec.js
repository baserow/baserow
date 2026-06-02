import { Editor } from '@tiptap/core'
import { CodeBlock } from '@tiptap/extension-code-block'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import { TextSelection } from '@tiptap/pm/state'
import {
  CodeAutoIndentExtension,
  getCodeAutoIndentText,
} from '@baserow/modules/core/editor/codeAutoIndentExtension'

const CodeEditorDocument = Document.extend({
  content: 'codeBlock',
})

function createEditor(code) {
  const editor = new Editor({
    extensions: [CodeEditorDocument, Text, CodeAutoIndentExtension, CodeBlock],
    content: {
      type: 'doc',
      content: [
        {
          type: 'codeBlock',
          content: code ? [{ type: 'text', text: code }] : [],
        },
      ],
    },
  })

  editor.view.dispatch(
    editor.state.tr.setSelection(TextSelection.atEnd(editor.state.doc))
  )

  return editor
}

describe('CodeAutoIndentExtension', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  it('keeps the current line indentation when pressing enter', () => {
    editor = createEditor('function test() {\n  return true')

    editor.commands.keyboardShortcut('Enter')

    expect(editor.getText()).toBe('function test() {\n  return true\n  ')
  })

  it('adds one indentation level after an opening delimiter', () => {
    editor = createEditor('if (true) {')

    editor.commands.keyboardShortcut('Enter')

    expect(editor.getText()).toBe('if (true) {\n  ')
  })

  it('computes indentation from the current line only', () => {
    expect(getCodeAutoIndentText('if (true) {\n  nested()', '  ')).toBe('\n  ')
  })
})
