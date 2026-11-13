import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { TestApp } from '@baserow/test/helpers/testApp'
import AgentApplicationSidebar from '@baserow/modules/agent/components/AgentApplicationSidebar'
import AgentConversationList from '@baserow/modules/agent/components/AgentConversationList'
import AgentMessage from '@baserow/modules/agent/components/AgentMessage'
import AgentTriggerStartCard from '@baserow/modules/agent/components/AgentTriggerStartCard'
import { nowKey } from '@baserow/modules/core/composables/useNow'

describe('Agent components', () => {
  let testApp

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('renders an untitled local draft as a new conversation with a Draft label', async () => {
    const wrapper = await testApp.mount(AgentConversationList, {
      props: {
        items: [
          { uuid: 'saved', title: 'Saved conversation' },
          { uuid: 'draft', title: '', local: true },
        ],
      },
    })
    const [saved, draft] = wrapper.findAll('.agent-conversations__item')

    expect(saved.text()).toBe('Saved conversation')
    expect(draft.text()).toContain('agent.newConversation')
    expect(draft.text()).toContain('agent.draft')
  })

  test('uses the shared footer with its saved message time and no feedback controls', async () => {
    const createdOn = '2026-11-03T10:00:00Z'
    const wrapper = await testApp.mount(AgentMessage, {
      props: {
        message: {
          role: 'assistant',
          content: '**Answer**',
          status: 'completed',
          created_on: createdOn,
        },
      },
      global: {
        provide: { [nowKey]: ref(Date.parse('2026-11-03T10:03:00Z')) },
      },
    })

    const footer = wrapper.get('.chat-message__footer')
    expect(footer.get('time').attributes('datetime')).toBe(createdOn)
    expect(footer.get('time').text()).toBe('datetime.minutesAgo - 3')
    expect(footer.findAll('button')).toHaveLength(1)
    expect(footer.get('button').attributes('aria-label')).toBe('action.copy')
  })

  test('shows loading, empty and error states without hiding loaded rows', async () => {
    const wrapper = await testApp.mount(AgentConversationList, {
      props: { items: [], loading: true },
    })
    expect(wrapper.get('aside').attributes('aria-busy')).toBe('true')
    expect(wrapper.get('.skeleton').attributes('aria-hidden')).toBe('true')
    expect(wrapper.findAll('.skeleton-block')).toHaveLength(8)
    expect(wrapper.find('[role="status"]').exists()).toBe(false)

    await wrapper.setProps({ loading: false })
    expect(wrapper.get('aside').attributes('aria-busy')).toBe('false')
    expect(wrapper.find('.skeleton').exists()).toBe(false)
    expect(wrapper.find('.agent-conversations__header').exists()).toBe(true)
    expect(wrapper.find('.agent-conversations__content').exists()).toBe(true)
    await wrapper.setProps({ error: true })
    await wrapper.get('.alert button').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
    await wrapper.setProps({
      error: false,
      loading: true,
      items: [{ uuid: 'conversation', title: 'My conversation' }],
    })

    expect(wrapper.get('.agent-conversations__item').text()).toBe(
      'My conversation'
    )
    expect(wrapper.find('[role="status"]').exists()).toBe(false)
  })

  test('shows the approvals waiting for the user as a sidebar counter', async () => {
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    const application = await testApp.store.dispatch(
      'application/forceCreate',
      {
        id: 10,
        name: 'Support agent',
        type: 'agent',
        workspace: { id: 1 },
        pending_count: 2,
      }
    )
    const wrapper = await testApp.mount(AgentApplicationSidebar, {
      props: {
        application,
        workspace: testApp.store.getters['workspace/get'](1),
      },
    })

    const counter = wrapper.get('.tree__counter')
    expect(counter.text()).toBe('2')
    expect(counter.classes()).toContain('badge-counter--warning')

    await testApp.store.dispatch('application/forceUpdate', {
      application,
      data: { pending_count: 0 },
    })
    await flushPromises()
    expect(wrapper.find('.tree__counter').exists()).toBe(false)
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

  test('shows a trigger start as a collapsed card named after its trigger type', async () => {
    const content =
      'Trigger data:\n```json\n{"triggered_at": "2026-11-09T09:00:00+00:00"}\n```'
    const wrapper = await testApp.mount(AgentMessage, {
      props: {
        message: {
          role: 'trigger',
          content,
          created_on: '2026-11-03T10:00:00Z',
        },
        triggerType: 'periodic',
      },
      global: {
        provide: { [nowKey]: ref(Date.parse('2026-11-03T10:03:00Z')) },
      },
    })
    const header = wrapper.get('.agent-trigger-start__header')
    const text = () => wrapper.get('.agent-trigger-start__text').text()

    expect(wrapper.find('.chat-message__bubble').exists()).toBe(false)
    expect(header.get('.agent-trigger-start__icon').classes()).toContain(
      'iconoir-timer'
    )
    expect(header.get('.agent-trigger-start__title').text()).toBe(
      'agent.startedBy'
    )
    expect(header.attributes('aria-expanded')).toBe('false')
    expect(text()).toBe('Trigger data:')
    await header.trigger('click')

    expect(header.attributes('aria-expanded')).toBe('true')
    expect(text()).toBe(content)
    expect(
      wrapper.get('.chat-message__footer time').attributes('datetime')
    ).toBe('2026-11-03T10:00:00Z')
  })

  test('names the start card after its trigger', async () => {
    const wrapper = await testApp.mount(AgentMessage, {
      props: {
        message: {
          role: 'trigger',
          content: 'Hello',
          created_on: '2026-11-03T10:00:00Z',
        },
        triggerType: 'periodic',
        triggerName: 'Morning digest',
      },
      global: {
        provide: { [nowKey]: ref(Date.parse('2026-11-03T10:03:00Z')) },
      },
    })

    expect(
      wrapper.findComponent(AgentTriggerStartCard).props('triggerName')
    ).toBe('Morning digest')
  })

  test('names the start card generically when its trigger type is gone', async () => {
    const wrapper = await testApp.mount(AgentMessage, {
      props: {
        message: {
          role: 'trigger',
          content: 'Hello',
          created_on: '2026-11-03T10:00:00Z',
        },
      },
      global: {
        provide: { [nowKey]: ref(Date.parse('2026-11-03T10:03:00Z')) },
      },
    })

    expect(wrapper.get('.agent-trigger-start__title').text()).toBe(
      'agent.startedByTrigger'
    )
    expect(wrapper.get('.agent-trigger-start__icon').classes()).toContain(
      'iconoir-flash'
    )
  })
})
