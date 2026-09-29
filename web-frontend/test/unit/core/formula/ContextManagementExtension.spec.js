import { Editor } from '@tiptap/core'
import { Document } from '@tiptap/extension-document'
import { Paragraph } from '@tiptap/extension-paragraph'
import { Text } from '@tiptap/extension-text'
import { ContextManagementExtension } from '@baserow/modules/core/components/formula/extensions/ContextManagementExtension'
import { NodeSelectionExtension } from '@baserow/modules/core/components/formula/extensions/NodeSelectionExtension'

function createEditor(rootEl, contextEl, options = {}) {
  return new Editor({
    extensions: [
      Document,
      Paragraph,
      Text,
      NodeSelectionExtension,
      ContextManagementExtension.configure({
        getRootEl: () => rootEl,
        getContextEl: () => contextEl,
        hideContextMenu: options.hideContextMenu ?? (() => {}),
      }),
    ],
    content: '<p></p>',
  })
}

describe('ContextManagementExtension', () => {
  let editor
  let rootEl
  let contextEl
  let outsideEl

  beforeEach(() => {
    rootEl = document.createElement('div')
    contextEl = document.createElement('div')
    outsideEl = document.createElement('div')
    rootEl.append(contextEl)
    document.body.append(rootEl, outsideEl)
  })

  afterEach(() => {
    editor?.destroy()
    rootEl.remove()
    outsideEl.remove()
  })

  it('removes every click-outside handler when the editor is destroyed', () => {
    editor = createEditor(rootEl, contextEl)

    // Focusing the editor and clicking its wrapper can each show the context.
    editor.commands.showContext()
    editor.commands.showContext()
    editor.destroy()
    editor = null

    const errors = []
    const onError = (event) => {
      errors.push(event.error)
      event.preventDefault()
    }
    window.addEventListener('error', onError)

    try {
      outsideEl.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
      outsideEl.dispatchEvent(new MouseEvent('click', { bubbles: true }))

      expect(errors).toEqual([])
    } finally {
      window.removeEventListener('error', onError)
    }
  })

  it('keeps a click-outside handler active after showing context twice', () => {
    const hideContextMenu = vi.fn()
    editor = createEditor(rootEl, contextEl, { hideContextMenu })

    editor.commands.showContext()
    editor.commands.showContext()

    outsideEl.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }))
    outsideEl.dispatchEvent(new MouseEvent('click', { bubbles: true }))

    expect(hideContextMenu).toHaveBeenCalledOnce()
  })
})
