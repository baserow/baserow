import { TestApp } from '@baserow/test/helpers/testApp'
import nodeStore from '@baserow/modules/automation/store/automationWorkflowNode'

const OLD_ADDRESS = 'old@inbound.baserow.io'
const NEW_ADDRESS = 'new@inbound.baserow.io'

describe('automationWorkflowNode update', () => {
  let testApp = null
  let store = null
  let workflow = null
  let node = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
    if (!store.hasModule('testNodes')) {
      store.registerModule('testNodes', nodeStore)
    }
    const trigger = {
      id: 1,
      type: 'email_trigger',
      workflow: 7,
      service: { id: 11, email_address: OLD_ADDRESS },
    }
    workflow = { id: 7, nodes: [], selectedNodeId: null }
    store.commit('testNodes/SET_ITEMS', { workflow, nodes: [trigger] })
    node = store.getters['testNodes/findById'](workflow, 1)
    // Freeze the clock: unlike `updateDebounced`, the request must reach the
    // server without any timer firing.
    vi.useFakeTimers()
  })

  afterEach(async () => {
    vi.useRealTimers()
    await testApp.afterEach()
  })

  test('sends the request straight away and shows loading for the round trip', async () => {
    let loadingDuringRequest = null
    testApp.mock.onPatch('automation/node/1/').reply(() => {
      loadingDuringRequest = store.getters['testNodes/getLoading'](node)
      return [
        200,
        {
          id: 1,
          type: 'email_trigger',
          workflow: 7,
          service: { id: 11, email_address: NEW_ADDRESS },
        },
      ]
    })

    await store.dispatch('testNodes/update', {
      workflow,
      node,
      values: { service: { ...node.service, regenerate_token: true } },
    })

    expect(testApp.mock.history.patch).toHaveLength(1)
    expect(JSON.parse(testApp.mock.history.patch[0].data)).toEqual({
      service: { id: 11, email_address: OLD_ADDRESS, regenerate_token: true },
    })
    expect(loadingDuringRequest).toBe(true)
    expect(store.getters['testNodes/getLoading'](node)).toBe(false)
    expect(node.service.email_address).toBe(NEW_ADDRESS)
    // The write-only flag is never stored on the node: only the server's
    // response is applied.
    expect(node.service.regenerate_token).toBeUndefined()
  })

  test('clears loading, leaves the node untouched and rethrows on failure', async () => {
    testApp.mock
      .onPatch('automation/node/1/')
      .reply(400, { error: 'ERROR_REQUEST_BODY_VALIDATION' })

    await expect(
      store.dispatch('testNodes/update', {
        workflow,
        node,
        values: { service: { ...node.service, regenerate_token: true } },
      })
    ).rejects.toThrow()

    expect(store.getters['testNodes/getLoading'](node)).toBe(false)
    expect(node.service.email_address).toBe(OLD_ADDRESS)
    expect(node.service.regenerate_token).toBeUndefined()
  })
})
