import CoreGotoServiceForm from '@baserow/modules/automation/components/services/CoreGotoServiceForm'

describe('CoreGotoServiceForm destinationNodes', () => {
  // A linear workflow: trigger -> before -> current (goto) -> after. Each node
  // carries a service, since a node is only a selectable destination once its
  // service (what `destination_service_id` points at) has landed.
  const trigger = { id: 1, type: 'trigger', service: { id: 11 } }
  const before = { id: 2, type: 'create_row', service: { id: 12 } }
  const current = { id: 3, type: 'goto', service: { id: 13 } }
  const after = { id: 4, type: 'create_row', service: { id: 14 } }
  const allNodes = [trigger, before, current, after]

  // The transitive previous nodes of each node on the linear path. Both the
  // backward check (destination in the goto's previous nodes) and the forward
  // check (goto in the destination's previous nodes) rely on this being
  // argument-aware.
  const previousByNodeId = {
    [trigger.id]: [],
    [before.id]: [trigger],
    [current.id]: [trigger, before],
    [after.id]: [trigger, before, current],
  }

  /**
   * Builds a minimal `this` context so the form's `destinationNodes` computed
   * can be exercised in isolation, without mounting the component or wiring up a
   * graph-backed store.
   */
  function makeContext() {
    return {
      workflow: { id: 1 },
      currentNode: current,
      $registry: {
        get: (kind, type) => ({ isTrigger: type === 'trigger' }),
      },
      $store: {
        getters: {
          'automationWorkflowNode/getNodes': () => allNodes,
          'automationWorkflowNode/getPreviousNodes': (workflow, node) =>
            previousByNodeId[node.id] ?? [],
          // Every node sits at the root level for this test.
          'automationWorkflowNode/getAncestors': () => [],
        },
      },
    }
  }

  const destinationNodes = (ctx) =>
    CoreGotoServiceForm.computed.destinationNodes.call(ctx)

  test('includes nodes that run before the Go to node (backward jump)', () => {
    expect(destinationNodes(makeContext()).map((node) => node.id)).toContain(
      before.id
    )
  })

  test('includes nodes that run after the Go to node (forward jump)', () => {
    expect(destinationNodes(makeContext()).map((node) => node.id)).toContain(
      after.id
    )
  })

  test('excludes the Go to node itself', () => {
    expect(
      destinationNodes(makeContext()).map((node) => node.id)
    ).not.toContain(current.id)
  })

  test('excludes trigger nodes', () => {
    expect(
      destinationNodes(makeContext()).map((node) => node.id)
    ).not.toContain(trigger.id)
  })
})

describe('CoreGotoServiceForm getNodeName', () => {
  const getNodeName = CoreGotoServiceForm.methods.getNodeName

  test('uses the node label when present', () => {
    const ctx = { $registry: { get: () => ({}) } }
    expect(
      getNodeName.call(ctx, { type: 'create_row', label: 'My node' })
    ).toBe('My node')
  })

  test('forwards the automation to getDefaultLabel for unlabeled nodes', () => {
    // A Go to node destination needs `automation` to resolve its own
    // destination label.
    const automation = { id: 99 }
    const getDefaultLabel = vi.fn(() => 'Go to node')
    const ctx = {
      automation,
      $registry: { get: () => ({ getDefaultLabel }) },
    }
    const node = { type: 'goto' }
    expect(getNodeName.call(ctx, node)).toBe('Go to node')
    expect(getDefaultLabel).toHaveBeenCalledWith({ automation, node })
  })
})

describe('CoreGotoServiceForm service watcher', () => {
  const watcher = CoreGotoServiceForm.watch.service

  test('adopts an externally cleared destination into the form values', () => {
    // The store cleared the link (a move took the destination off the goto's path).
    const ctx = { values: { destination_service_id: 2 } }
    watcher.call(ctx, { destination_service_id: null })
    expect(ctx.values.destination_service_id).toBeNull()
  })

  test('leaves the form values untouched when nothing changed', () => {
    const values = { destination_service_id: 2 }
    const ctx = { values }
    watcher.call(ctx, { destination_service_id: 2 })
    // Same reference, unchanged — no redundant write that could loop.
    expect(ctx.values).toBe(values)
    expect(ctx.values.destination_service_id).toBe(2)
  })

  test('treats a missing service as no destination', () => {
    const ctx = { values: { destination_service_id: 2 } }
    watcher.call(ctx, null)
    expect(ctx.values.destination_service_id).toBeNull()
  })
})
