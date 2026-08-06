import { TestApp } from '@baserow/test/helpers/testApp'

describe('Integration store', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('update merges server-generated fields into the integration', async () => {
    const integration = {
      id: 1,
      type: 'local_baserow',
      name: 'Local Baserow',
      authorized_user: { id: 2, username: 'user@example.com' },
      authorized_agent: null,
      context_data: { databases: [] },
    }
    const application = { id: 10, integrations: [integration] }
    const updatedIntegration = {
      ...integration,
      authorized_agent: { id: 3, name: 'Writer agent' },
      context_data: { databases: [{ id: 4, name: 'Agent database' }] },
    }
    testApp.mock.onPatch('/integration/1/').reply(200, updatedIntegration)

    await testApp.store.dispatch('integration/update', {
      application,
      integrationId: integration.id,
      values: { authorized_agent_id: 3 },
    })

    expect(application.integrations).toEqual([updatedIntegration])
  })
})
