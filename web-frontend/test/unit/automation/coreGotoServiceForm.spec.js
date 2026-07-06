import CoreGotoServiceForm from '@baserow/modules/automation/components/services/CoreGotoServiceForm'

describe('CoreGotoServiceForm destinationNodes', () => {
  // A linear workflow: trigger -> before -> current (goto) -> after
  const trigger = { id: 1, type: 'trigger' }
  const before = { id: 2, type: 'create_row' }
  const current = { id: 3, type: 'goto_node' }
  const after = { id: 4, type: 'create_row' }
  const allNodes = [trigger, before, current, after]

  /**
   * Builds a minimal `this` context so the form's `destinationNodes` computed
   * can be exercised in isolation, without mounting the component or wiring up a
   * graph-backed store. `previousNodes` are the nodes that run before `current`.
   */
  function makeContext(previousNodes) {
    return {
      workflow: { id: 1 },
      currentNode: current,
      $registry: {
        get: (kind, type) => ({ isTrigger: type === 'trigger' }),
      },
      $store: {
        getters: {
          'automationWorkflowNode/getNodes': () => allNodes,
          'automationWorkflowNode/getPreviousNodes': () => previousNodes,
          // Every node sits at the root level for this test.
          'automationWorkflowNode/getAncestors': () => [],
        },
      },
    }
  }

  const destinationNodes = (ctx) =>
    CoreGotoServiceForm.computed.destinationNodes.call(ctx)

  test('includes nodes that run before the Go to node (backward jump)', () => {
    const ctx = makeContext([trigger, before])
    expect(destinationNodes(ctx).map((node) => node.id)).toEqual([before.id])
  })

  test('excludes nodes that run after the Go to node (forward jump)', () => {
    const ctx = makeContext([trigger, before])
    expect(destinationNodes(ctx).map((node) => node.id)).not.toContain(after.id)
  })

  test('excludes the Go to node itself', () => {
    // Even if the node somehow appeared in its own previous nodes, it is filtered.
    const ctx = makeContext([trigger, before, current])
    expect(destinationNodes(ctx).map((node) => node.id)).not.toContain(
      current.id
    )
  })

  test('excludes trigger nodes', () => {
    const ctx = makeContext([trigger, before])
    expect(destinationNodes(ctx).map((node) => node.id)).not.toContain(
      trigger.id
    )
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
    const node = { type: 'goto_node' }
    expect(getNodeName.call(ctx, node)).toBe('Go to node')
    expect(getDefaultLabel).toHaveBeenCalledWith({ automation, node })
  })
})

describe('CoreGotoServiceForm service watcher', () => {
  const watcher = CoreGotoServiceForm.watch.service

  test('adopts an externally cleared destination into the form values', () => {
    // The store cleared the link (the move turned it into a forward jump).
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
