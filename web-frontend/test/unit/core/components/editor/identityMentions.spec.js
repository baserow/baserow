import { nextTick } from 'vue'
import suggestion from '@baserow/modules/core/editor/suggestion'
import { TestApp } from '@baserow/test/helpers/testApp'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import RichTextEditorMentionsList from '@baserow/modules/core/components/editor/RichTextEditorMentionsList'

describe('Identity User mentions', () => {
  let testApp
  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      users: [{ id: 10, user_id: 20, name: 'Person' }],
      identities: [{ id: 30, name: 'Ops', user_type: 'identity' }],
    })
  })
  afterEach(async () => {
    await testApp.afterEach()
  })

  test('a name refresh updates the open editor without saving content', async () => {
    const wrapper = await testApp.mount(RichTextEditor, {
      props: {
        modelValue: 'Ask @30',
        enableRichTextFormatting: true,
        mentionableUsers:
          testApp.store.getters['workspace/getCollaborators'](1),
      },
    })
    expect(wrapper.find('[data-type="mention"]').text()).toBe('@Ops')
    await wrapper.setProps({
      mentionableUsers: [
        { user_id: 30, name: 'Support', user_type: 'identity' },
      ],
    })
    expect(wrapper.find('[data-type="mention"]').text()).toBe('@Support')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  test('an open suggestion popup follows realtime Identity names and removal', async () => {
    const popup = suggestion({
      users: () => testApp.store.getters['workspace/getCollaborators'](1),
    }).render()
    popup.onStart({
      editor: { appContext: testApp.getApp().vueApp._context },
      query: 'ops',
      command: vi.fn(),
      clientRect: () => new DOMRect(0, 0, 10, 10),
    })
    try {
      await nextTick()
      expect(
        testApp.body.find('.rich-text-editor__mention-list').text()
      ).toContain('Ops')
      testApp.store.commit('workspace/UPSERT_WORKSPACE_IDENTITY', {
        workspaceId: 1,
        identity: { id: 30, name: 'Renamed Ops', user_type: 'identity' },
      })
      await nextTick()
      expect(
        testApp.body.find('.rich-text-editor__mention-list').text()
      ).toContain('Renamed Ops')
      testApp.store.commit('workspace/DELETE_WORKSPACE_IDENTITY', {
        workspaceId: 1,
        identityId: 30,
      })
      await nextTick()
      expect(
        testApp.body.find('.rich-text-editor__mention-list').exists()
      ).toBe(false)
    } finally {
      popup.onExit()
    }
  })

  test('the suggestion list selects the Identity User ID and renders its icon', async () => {
    const command = vi.fn()
    const wrapper = await testApp.mount(RichTextEditorMentionsList, {
      props: {
        users: testApp.store.getters['workspace/getCollaborators'](1),
        query: 'ops',
        command,
      },
    })
    expect(wrapper.findAll('li')).toHaveLength(1)
    expect(wrapper.find('.iconoir-lock').exists()).toBe(true)
    await wrapper.find('li').trigger('click')
    expect(command).toHaveBeenCalledWith({ id: 30, label: 'Ops' })

    testApp.store.commit('workspace/DELETE_WORKSPACE_IDENTITY', {
      workspaceId: 1,
      identityId: 30,
    })
    await wrapper.setProps({
      users: testApp.store.getters['workspace/getCollaborators'](1),
    })
    expect(wrapper.findAll('li')).toHaveLength(0)
    testApp.store.commit('workspace/UPSERT_WORKSPACE_IDENTITY', {
      workspaceId: 1,
      identity: { id: 30, name: 'Restored Ops', user_type: 'identity' },
    })
    await wrapper.setProps({
      users: testApp.store.getters['workspace/getCollaborators'](1),
    })
    expect(wrapper.find('li').text()).toContain('Restored Ops')
  })
})
