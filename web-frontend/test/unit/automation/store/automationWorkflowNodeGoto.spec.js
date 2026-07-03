import nodeStore from '@baserow/modules/automation/store/automationWorkflowNode'

const clearInvalidatedGotoLinks = nodeStore.actions.clearInvalidatedGotoLinks

describe('clearInvalidatedGotoLinks', () => {
  const workflow = { id: 1 }
  const trigger = { id: 1, type: 'trigger' }
  const destination = { id: 2, type: 'create_row' }

  const makeGoto = () => ({
    id: 3,
    type: 'goto_node',
    service: { condition: {}, destination_node_id: destination.id },
  })

  /**
   * Runs the action against a mocked Vuex context. `previousNodes` are the
   * nodes the store reports as running before the Go to node.
   */
  function run(previousNodes) {
    const goto = makeGoto()
    const nodes = [trigger, destination, goto]
    const dispatched = []
    const dispatch = (name, payload) => dispatched.push({ name, payload })
    const getters = {
      getNodes: () => nodes,
      getAncestors: () => [],
      getPreviousNodes: () => previousNodes,
      findById: (_workflow, id) => nodes.find((node) => node.id === id) || null,
    }
    const thisArg = {
      $registry: { get: (kind, type) => ({ isTrigger: type === 'trigger' }) },
    }
    clearInvalidatedGotoLinks.call(thisArg, { dispatch, getters }, { workflow })
    return dispatched
  }

  test('clears a link that became a forward jump', () => {
    // The destination no longer runs before the Go to node.
    const dispatched = run([])
    expect(dispatched).toHaveLength(1)
    expect(dispatched[0].name).toBe('forceUpdate')
    expect(dispatched[0].payload.node.id).toBe(3)
    expect(dispatched[0].payload.values.service.destination_node_id).toBeNull()
  })

  test('keeps a valid backward jump untouched', () => {
    // The destination still runs before the Go to node.
    const dispatched = run([trigger, destination])
    expect(dispatched).toHaveLength(0)
  })
})
