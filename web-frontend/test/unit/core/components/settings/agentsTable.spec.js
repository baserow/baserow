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

  test('uses the paginated response total in the heading', async () => {
    testApp.mock.onGet('/agents/workspace/1/').replyOnce(200, {
      count: 250,
      results: [
        {
          id: 10,
          name: 'First page agent',
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
    await flushPromises()

    expect(wrapper.vm.count).toBe(250)
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

  test.each([
    [['agent.create'], 2, 3, false, false],
    [['agent.update'], 0, 4, true, false],
    [['agent.delete'], 0, 4, false, true],
    [[], 0, 3, false, false],
  ])(
    'shows controls for independent Agent permissions: %s',
    async (
      permissions,
      createButtonCount,
      columnCount,
      showsEdit,
      showsDelete
    ) => {
      const agent = { id: 10, workspace_id: 1, name: 'Writer' }
      await testApp.store.dispatch('agent/forceCreate', agent)
      const wrapper = await testApp.mount(AgentsTable, {
        props: {
          workspace: { id: 1, name: 'Workspace', _: { roles: [] } },
        },
        global: {
          mocks: {
            $hasPermission: (operation) => permissions.includes(operation),
          },
          stubs: {
            CrudTable: {
              name: 'CrudTable',
              props: ['columns'],
              data: () => ({ agent }),
              template: `
                <div>
                  <slot name="empty" />
                  <slot name="header-right-side" />
                  <span class="column-count">{{ columns.length }}</span>
                  <button class="open-row" @click="$emit('row-context', { row: agent, target: $el })">Open row</button>
                  <slot name="menus" />
                </div>
              `,
              methods: { refresh() {} },
            },
            Context: {
              template: '<div><slot /></div>',
              methods: { show() {}, hide() {} },
            },
            ManageAgentModal: {
              name: 'ManageAgentModal',
              props: ['agent'],
              template:
                '<div class="agent-modal">{{ agent ? "update" : "create" }}</div>',
              methods: { show() {} },
            },
          },
        },
      })

      expect(
        wrapper
          .findAll('button')
          .filter((button) => button.text() === 'agents.create')
      ).toHaveLength(createButtonCount)
      expect(wrapper.find('.column-count').text()).toBe(String(columnCount))

      await wrapper.find('.open-row').trigger('click')
      await flushPromises()
      expect(wrapper.text().includes('agents.edit')).toBe(showsEdit)
      expect(wrapper.text().includes('agents.delete')).toBe(showsDelete)
      expect(
        wrapper
          .findAll('.agent-modal')
          .some((modal) => modal.text() === 'update')
      ).toBe(showsEdit)
    }
  )
})
