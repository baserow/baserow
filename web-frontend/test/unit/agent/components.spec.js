import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentApplicationSidebar from '@baserow/modules/agent/components/AgentApplicationSidebar'
import AgentConversationList from '@baserow/modules/agent/components/AgentConversationList'

describe('Agent components', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('uses idle status dots for saved conversations and local drafts', async () => {
    const items = [
      { uuid: 'saved-thread', title: 'Saved conversation' },
      { uuid: 'draft-thread', title: 'Local conversation', local: true },
    ]
    const wrapper = await testApp.mount(AgentConversationList, {
      props: { items, selected: 'saved-thread' },
    })
    const rows = wrapper.findAll('.agent-conversations__item')
    expect(rows).toHaveLength(2)
    for (const row of rows) {
      const status = row.get('.agent-conversations__status--idle')
      expect(status.attributes('aria-hidden')).toBe('true')
      expect(row.find('.iconoir-chat-bubble').exists()).toBe(false)
    }
    expect(rows[0].attributes('aria-current')).toBe('true')
    expect(rows[0].text()).toBe('Saved conversation')
    expect(rows[1].text()).toContain('Local conversation')
    await rows[1].trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual([items[1]])
  })

  test('shows loading, empty and error states without hiding loaded rows', async () => {
    const wrapper = await testApp.mount(AgentConversationList, {
      props: { items: [], loading: true },
    })
    const hint = wrapper.get('[role="status"]')
    expect(hint.text()).toBe('agent.loadingConversations')

    await wrapper.setProps({ loading: false })
    expect(wrapper.get('[role="status"]').element).toBe(hint.element)
    expect(hint.text()).toBe('agent.noConversations')
    await wrapper.setProps({ error: true })
    await wrapper.get('.alert button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    await wrapper.setProps({
      error: false,
      loading: true,
      items: [{ uuid: 'thread', title: 'My conversation' }],
    })

    expect(wrapper.get('.agent-conversations__item').text()).toBe(
      'My conversation'
    )
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
    expect(wrapper.find('.loading').exists()).toBe(false)
  })

  test('renames the agent through the standard application context', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    const agent = { id: 10, name: 'Support agent', type: 'agent' }
    const application = await testApp.store.dispatch(
      'application/forceCreate',
      { ...agent, workspace: { id: 1 } }
    )
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
    testApp.mock.onGet('/workspaces/1/roles/').reply(200, [])
    testApp.mock
      .onPatch('/applications/10/')
      .reply(200, { ...agent, name: 'Support assistant' })
    const wrapper = await testApp.mount(AgentApplicationSidebar, {
      props: {
        application,
        workspace: testApp.store.getters['workspace/get'](1),
      },
    })

    await wrapper.find('.tree__options').trigger('click')
    await flushPromises()
    await wrapper
      .findAll('.context__menu-item-link')
      .find((link) => link.text() === 'sidebarApplication.rename')
      .trigger('click')
    const editable = wrapper.find('[contenteditable="true"]')
    editable.element.textContent = 'Support assistant'
    await editable.trigger('input')
    await editable.trigger('keydown', { key: 'Enter' })
    await flushPromises()

    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      name: 'Support assistant',
    })
    expect(wrapper.find('.tree__link').attributes('aria-label')).toBe(
      'Support assistant'
    )
  })
})
