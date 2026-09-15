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
})
