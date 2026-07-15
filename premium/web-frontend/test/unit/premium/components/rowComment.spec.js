import flushPromises from 'flush-promises'

import { PremiumTestApp } from '@baserow_premium_test/helpers/premiumTestApp'
import RowComment from '@baserow_premium/components/row_comments/RowComment'
import RowCommentContext from '@baserow_premium/components/row_comments/RowCommentContext'

describe('RowComment component', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new PremiumTestApp()
  })

  afterEach(() => testApp.afterEach())

  const message = {
    type: 'doc',
    content: [
      {
        type: 'paragraph',
        content: [
          { type: 'text', text: 'Ping ' },
          { type: 'mention', attrs: { id: '5', label: 'Jane Doe' } },
          { type: 'hardBreak' },
          { type: 'text', text: 'second line' },
        ],
      },
    ],
  }

  const comment = {
    id: 1,
    user_id: 999,
    first_name: 'John',
    created_on: '2024-01-01T10:00:00Z',
    updated_on: '2024-01-01T10:00:00Z',
    edited: false,
    trashed: false,
    isTemporary: false,
    message,
  }

  const mountComponent = (props = {}) =>
    testApp.mount(RowComment, {
      props: {
        comment,
        workspace: { id: 30, users: [{ user_id: 5, name: 'Jane Doe' }] },
        canEdit: true,
        canDelete: true,
        ...props,
      },
    })

  test('renders the stored comment document read-only', async () => {
    const wrapper = await mountComponent()
    const editor = wrapper.find('.tiptap')

    expect(editor.attributes('contenteditable')).toBe('false')
    expect(editor.text()).toContain('Ping')
    expect(editor.text()).toContain('second line')
    expect(editor.find('br').exists()).toBe(true)

    const mention = wrapper.find('.rich-text-editor__mention')
    expect(mention.text()).toBe('@Jane Doe')
  })

  test('saving without any edits does not dispatch an update', async () => {
    const wrapper = await mountComponent()
    const dispatch = vi
      .spyOn(testApp.getStore(), 'dispatch')
      .mockResolvedValue()

    wrapper.findComponent(RowCommentContext).vm.$emit('edit')
    await flushPromises()

    expect(wrapper.find('.tiptap').attributes('contenteditable')).toBe('true')
    expect(wrapper.find('.row-comments__comment-text-actions').exists()).toBe(
      true
    )

    await wrapper.find('.tiptap').trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(wrapper.find('.tiptap').attributes('contenteditable')).toBe('false')
    expect(wrapper.find('.row-comments__comment-text-actions').exists()).toBe(
      false
    )
    expect(dispatch).not.toHaveBeenCalledWith(
      'row_comments/updateComment',
      expect.anything()
    )
  })

  test('saving after a real edit dispatches an update', async () => {
    const wrapper = await mountComponent()
    const dispatch = vi
      .spyOn(testApp.getStore(), 'dispatch')
      .mockResolvedValue()

    wrapper.findComponent(RowCommentContext).vm.$emit('edit')
    await flushPromises()

    wrapper
      .findComponent({ name: 'RichTextEditor' })
      .vm.editor.commands.insertContent('changed ')
    await wrapper.find('.tiptap').trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(dispatch).toHaveBeenCalledWith(
      'row_comments/updateComment',
      expect.objectContaining({ commentId: comment.id })
    )
  })
})
