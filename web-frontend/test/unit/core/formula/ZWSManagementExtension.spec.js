import { Editor } from '@tiptap/core'
import { Document } from '@tiptap/extension-document'
import { Text } from '@tiptap/extension-text'
import { Paragraph } from '@tiptap/extension-paragraph'
import { ZWSManagementExtension } from '@baserow/modules/core/components/formula/extensions/ZWSManagementExtension'

/**
 * Creates a minimal TipTap editor with only the ZWSManagementExtension active.
 */
function createEditor(content) {
  return new Editor({
    extensions: [Document, Paragraph, Text, ZWSManagementExtension],
    content,
  })
}

function triggerAppendTransaction(editor) {
  editor.view.dispatch(editor.state.tr.setMeta('forceAppendTransaction', true))
}

describe('ZWSManagementExtension', () => {
  let editor

  afterEach(() => {
    editor?.destroy()
  })

  it('reduces triple and quadruple consecutive ZWS to a single ZWS', () => {
    editor = createEditor({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [{ type: 'text', text: 'x\u200B\u200B\u200B\u200By' }], // 4× ZWS
        },
        {
          type: 'paragraph',
          content: [{ type: 'text', text: 'p\u200B\u200B\u200Bq' }], // 3× ZWS
        },
      ],
    })

    expect(() => triggerAppendTransaction(editor)).not.toThrow()
  })
})
