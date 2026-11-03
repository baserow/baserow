import { nextTick } from 'vue'
import suggestion from '@baserow/modules/core/editor/suggestion'
import { TestApp } from '@baserow/test/helpers/testApp'
import RichTextEditor from '@baserow/modules/core/components/editor/RichTextEditor'
import RichTextEditorMentionsList from '@baserow/modules/core/components/editor/RichTextEditorMentionsList'

describe('Agent User mentions', () => {
  let testApp
  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      users: [{ id: 10, user_id: 20, name: 'Person' }],
      agents: [{ id: 30, name: 'Ops', identity_type: 'agent' }],
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
        { user_id: 30, name: 'Support', identity_type: 'agent' },
      ],
    })
    expect(wrapper.find('[data-type="mention"]').text()).toBe('@Support')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  test('an open suggestion popup follows realtime Agent names and removal', async () => {
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
      testApp.store.commit('workspace/UPSERT_WORKSPACE_AGENT', {
        workspaceId: 1,
        agent: { id: 30, name: 'Renamed Ops', identity_type: 'agent' },
      })
      await nextTick()
      expect(
        testApp.body.find('.rich-text-editor__mention-list').text()
      ).toContain('Renamed Ops')
      testApp.store.commit('workspace/DELETE_WORKSPACE_AGENT', {
        workspaceId: 1,
        agentId: 30,
      })
      await nextTick()
      expect(
        testApp.body.find('.rich-text-editor__mention-list').exists()
      ).toBe(false)
    } finally {
      popup.onExit()
    }
  })

  test('the suggestion list selects the Agent User ID and renders its icon', async () => {
    const command = vi.fn()
    const wrapper = await testApp.mount(RichTextEditorMentionsList, {
      props: {
        users: testApp.store.getters['workspace/getCollaborators'](1),
        query: 'ops',
        command,
      },
    })
    expect(wrapper.findAll('li')).toHaveLength(1)
    expect(wrapper.find('.baserow-icon-agent').exists()).toBe(true)
    await wrapper.find('li').trigger('click')
    expect(command).toHaveBeenCalledWith({ id: 30, label: 'Ops' })

    testApp.store.commit('workspace/DELETE_WORKSPACE_AGENT', {
      workspaceId: 1,
      agentId: 30,
    })
    await wrapper.setProps({
      users: testApp.store.getters['workspace/getCollaborators'](1),
    })
    expect(wrapper.findAll('li')).toHaveLength(0)
    testApp.store.commit('workspace/UPSERT_WORKSPACE_AGENT', {
      workspaceId: 1,
      agent: { id: 30, name: 'Restored Ops', identity_type: 'agent' },
    })
    await wrapper.setProps({
      users: testApp.store.getters['workspace/getCollaborators'](1),
    })
    expect(wrapper.find('li').text()).toContain('Restored Ops')
  })
})
