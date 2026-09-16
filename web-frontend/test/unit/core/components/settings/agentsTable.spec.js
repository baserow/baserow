import flushPromises from 'flush-promises'

import AgentsTable from '@baserow/modules/core/components/settings/agents/AgentsTable'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('AgentsTable', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('refreshes when an agent is restored in its workspace', async () => {
    testApp.mock
      .onGet('/agents/workspace/1/')
      .replyOnce(200, { count: 0, results: [] })
      .onGet('/agents/workspace/1/')
      .replyOnce(200, {
        count: 1,
        results: [
          {
            id: 10,
            name: 'Restored agent',
            last_active: null,
            role_uid: 'NO_ACCESS',
          },
        ],
      })
    const wrapper = await testApp.mount(AgentsTable, {
      props: {
        workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
      },
    })

    expect(wrapper.text()).not.toContain('Restored agent')

    await testApp.store.dispatch('agent/forceCreate', {
      id: 10,
      workspace_id: 1,
      name: 'Restored agent',
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Restored agent')
  })

  test('passes realtime updates to the selected editor through its agent prop', async () => {
    const agent = {
      id: 10,
      workspace_id: 1,
      name: 'Writer',
      teams: [{ id: 3 }],
    }
    await testApp.store.dispatch('agent/forceCreate', agent)
    const wrapper = await testApp.mount(
      {
        ...AgentsTable,
        computed: { ...AgentsTable.computed, canManage: () => true },
      },
      {
        props: { workspace: { id: 1, name: 'Workspace', _: { roles: [] } } },
        global: {
          stubs: {
            CrudTable: {
              name: 'CrudTable',
              template: '<div><slot name="menus" /></div>',
              methods: { refresh() {} },
            },
            AgentContext: {
              name: 'AgentContext',
              template: '<div />',
              methods: { show() {} },
            },
            ManageAgentModal: {
              name: 'ManageAgentModal',
              props: ['agent'],
              template: '<div />',
            },
          },
        },
      }
    )
    wrapper
      .findComponent({ name: 'CrudTable' })
      .vm.$emit('row-context', { row: agent, target: document.body })
    await flushPromises()
    const editor = () =>
      wrapper
        .findAllComponents({ name: 'ManageAgentModal' })
        .find((modal) => modal.props('agent'))
    expect(editor().props('agent').teams).toEqual([{ id: 3 }])

    await testApp.store.dispatch('agent/forceUpdate', { ...agent, teams: [] })
    await flushPromises()
    expect(editor().props('agent').teams).toEqual([])
  })
})
