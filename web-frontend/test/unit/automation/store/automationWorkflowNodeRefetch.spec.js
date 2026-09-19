import { TestApp } from '@baserow/test/helpers/testApp'
import nodeStore from '@baserow/modules/automation/store/automationWorkflowNode'

describe('automationWorkflowNode refetch', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    if (!store.hasModule('testNodes')) {
      store.registerModule('testNodes', nodeStore)
    }
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('reloads only the requested node and keeps the selection', async () => {
    const trigger = {
      id: 1,
      type: 'email_trigger',
      workflow: 7,
      service: { id: 11, sample_data: null },
    }
    const action = {
      id: 2,
      type: 'create_row',
      workflow: 7,
      service: { id: 12, sample_data: null },
    }
    const workflow = { id: 7, nodes: [], selectedNodeId: null }
    store.commit('testNodes/SET_ITEMS', { workflow, nodes: [trigger, action] })
    workflow.selectedNodeId = 1

    const freshSample = { data: { subject: 'Big HTML payload test' } }
    testApp.mock.onGet('/automation/workflow/7/nodes/').reply(200, [
      { ...trigger, service: { id: 11, sample_data: freshSample } },
      { ...action, label: 'server-side label' },
    ])

    const updated = await store.dispatch('testNodes/refetch', {
      workflow,
      nodeId: 1,
    })

    expect(updated.service.sample_data).toEqual(freshSample)
    expect(workflow.selectedNodeId).toBe(1)
    // Only the requested node is touched.
    expect(
      store.getters['testNodes/findById'](workflow, 2).label
    ).toBeUndefined()
  })

  test('is a no-op when the node no longer exists', async () => {
    const workflow = { id: 7, nodes: [], selectedNodeId: null }
    store.commit('testNodes/SET_ITEMS', { workflow, nodes: [] })
    testApp.mock.onGet('/automation/workflow/7/nodes/').reply(200, [])

    await expect(
      store.dispatch('testNodes/refetch', { workflow, nodeId: 99 })
    ).resolves.toBeNull()
  })
})
