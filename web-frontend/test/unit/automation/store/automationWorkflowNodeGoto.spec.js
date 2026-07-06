import nodeStore from '@baserow/modules/automation/store/automationWorkflowNode'

const clearInvalidatedGotoLinks = nodeStore.actions.clearInvalidatedGotoLinks

describe('clearInvalidatedGotoLinks', () => {
  const workflow = { id: 1 }
  const trigger = { id: 1, type: 'trigger' }
  const destination = { id: 2, type: 'create_row', service: { id: 20 } }

  const makeGoto = () => ({
    id: 3,
    type: 'goto',
    service: { condition: {}, destination_service_id: destination.service.id },
  })

  /**
   * Runs the action against a mocked Vuex context. `previousByNodeId` maps a
   * node id to the nodes the store reports as running before it, so both the
   * backward and forward jump checks can be exercised.
   */
  function run(previousByNodeId) {
    const goto = makeGoto()
    const nodes = [trigger, destination, goto]
    const dispatched = []
    const dispatch = (name, payload) => dispatched.push({ name, payload })
    const getters = {
      getNodes: () => nodes,
      getAncestors: () => [],
      getPreviousNodes: (_workflow, node) => previousByNodeId[node.id] ?? [],
      findByServiceId: (_workflow, serviceId) =>
        nodes.find((node) => node.service?.id === serviceId) || null,
    }
    const thisArg = {
      $registry: { get: (kind, type) => ({ isTrigger: type === 'trigger' }) },
    }
    clearInvalidatedGotoLinks.call(thisArg, { dispatch, getters }, { workflow })
    return dispatched
  }

  test('clears a link whose destination left the Go to node path', () => {
    // The destination is on neither the goto's backward nor its forward path.
    const dispatched = run({ 2: [trigger], 3: [trigger] })
    expect(dispatched).toHaveLength(1)
    expect(dispatched[0].name).toBe('forceUpdate')
    expect(dispatched[0].payload.node.id).toBe(3)
    expect(
      dispatched[0].payload.values.service.destination_service_id
    ).toBeNull()
  })

  test('keeps a valid backward jump untouched', () => {
    // The destination still runs before the Go to node.
    const dispatched = run({ 2: [trigger], 3: [trigger, destination] })
    expect(dispatched).toHaveLength(0)
  })

  test('keeps a valid forward jump untouched', () => {
    // The destination now runs after the Go to node - a valid forward jump.
    const dispatched = run({ 2: [trigger, { id: 3 }], 3: [trigger] })
    expect(dispatched).toHaveLength(0)
  })
})
