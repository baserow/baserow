import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'
import { selectAgentApplication } from '@baserow/modules/agent/middleware/selectAgentApplication'

describe('selectAgentApplication', () => {
  let testApp

  beforeEach(async () => {
    testApp = new TestApp()
    await testApp.store.dispatch('workspace/forceCreate', {
      id: 1,
      name: 'Workspace',
    })
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  async function select(type, canRead) {
    await testApp.store.dispatch('application/forceCreate', {
      id: 10,
      name: 'Application',
      type,
      tables: [],
      workspace: { id: 1 },
    })
    const workspace = testApp.store.getters['workspace/get'](1)
    // Opening from All workspaces starts before workspace permissions load.
    const $hasPermission = () => workspace._.permissionsLoaded && canRead
    return selectAgentApplication(
      { $store: testApp.store, $hasPermission },
      { params: { agentId: '10' } }
    )
  }

  test('selects a readable agent after loading its workspace permissions', async () => {
    await select('agent', true)

    expect(testApp.store.getters['application/getSelected'].id).toBe(10)
    expect(testApp.store.getters['workspace/getSelected'].id).toBe(1)
  })

  test.each([
    ['database', true],
    ['agent', false],
  ])('rejects a %s with read access=%s', async (type, canRead) => {
    await expect(select(type, canRead)).rejects.toMatchObject({
      statusCode: 404,
    })
    expect(testApp.store.getters['application/getSelected']).toBeNull()
  })
})
