import {
  buildGotoDestinations,
  isBackwardGotoJump,
  isValidGotoDestination,
} from '@baserow/modules/automation/utils/gotoNode'

describe('isValidGotoDestination', () => {
  // A linear workflow: trigger -> before -> goto -> after, all at root level.
  const trigger = { id: 1, type: 'trigger' }
  const before = { id: 2, type: 'create_row' }
  const goto = { id: 3, type: 'goto' }
  const after = { id: 4, type: 'create_row' }

  const isTrigger = (node) => node.type === 'trigger'
  const noAncestors = () => []
  // The transitive previous nodes of each node on the linear path.
  const previousByNodeId = {
    [trigger.id]: [],
    [before.id]: [trigger],
    [goto.id]: [trigger, before],
    [after.id]: [trigger, before, goto],
  }
  const previousNodesOf = (node) => previousByNodeId[node.id] ?? []

  const validate = (destinationNode, overrides = {}) =>
    isValidGotoDestination({
      gotoNode: goto,
      destinationNode,
      ancestorsOf: noAncestors,
      previousNodesOf,
      isTrigger,
      ...overrides,
    })

  test('accepts a same-level node that runs before (backward jump)', () => {
    expect(validate(before)).toBe(true)
  })

  test('accepts a same-level node that runs after (forward jump)', () => {
    expect(validate(after)).toBe(true)
  })

  test('rejects the Go to node itself', () => {
    expect(validate(goto)).toBe(false)
  })

  test('rejects a trigger node', () => {
    expect(validate(trigger)).toBe(false)
  })

  test('rejects a missing destination', () => {
    expect(validate(null)).toBe(false)
  })

  test('rejects a node at a different level', () => {
    // `before` now sits inside a container, so its ancestor chain differs.
    const ancestorsOf = (node) => (node.id === before.id ? [{ id: 9 }] : [])
    expect(validate(before, { ancestorsOf })).toBe(false)
  })

  test('rejects a same-level node on a different branch (off-path)', () => {
    // `sibling` shares the goto's level but is on neither its backward nor its
    // forward path: it is in nobody's previous nodes along the goto's chain.
    const sibling = { id: 5, type: 'create_row' }
    expect(validate(sibling)).toBe(false)
  })
})

describe('isBackwardGotoJump', () => {
  // A linear workflow: before -> goto -> after.
  const before = { id: 2 }
  const goto = { id: 3 }
  const after = { id: 4 }
  const previousByNodeId = {
    [before.id]: [],
    [goto.id]: [before],
    [after.id]: [before, goto],
  }
  const previousNodesOf = (node) => previousByNodeId[node.id] ?? []

  test('is true when the destination runs before the Go to node', () => {
    expect(
      isBackwardGotoJump({
        gotoNode: goto,
        destinationNode: before,
        previousNodesOf,
      })
    ).toBe(true)
  })

  test('is false when the destination runs after the Go to node', () => {
    expect(
      isBackwardGotoJump({
        gotoNode: goto,
        destinationNode: after,
        previousNodesOf,
      })
    ).toBe(false)
  })
})

describe('buildGotoDestinations', () => {
  // A linear workflow: trigger -> before -> goto -> after. Each node carries a
  // service, since a node is only a selectable destination once its service
  // (what `destination_service_id` points at) has landed. `pending` is an
  // optimistically created node that has no service yet.
  const trigger = { id: 1, type: 'trigger', service: { id: 11 } }
  const before = { id: 2, type: 'create_row', service: { id: 12 } }
  const goto = { id: 3, type: 'goto', service: { id: 13 } }
  const after = { id: 4, type: 'create_row', service: { id: 14 } }
  const pending = { id: 5, type: 'create_row', service: null }
  const nodes = [trigger, before, goto, after, pending]

  const isTrigger = (node) => node.type === 'trigger'
  const noAncestors = () => []
  const previousByNodeId = {
    [trigger.id]: [],
    [before.id]: [trigger],
    [goto.id]: [trigger, before],
    [after.id]: [trigger, before, goto],
    [pending.id]: [trigger, before, goto, after],
  }
  const previousNodesOf = (node) => previousByNodeId[node.id] ?? []

  const build = (overrides = {}) =>
    buildGotoDestinations({
      gotoNode: goto,
      nodes,
      ancestorsOf: noAncestors,
      previousNodesOf,
      isTrigger,
      nameOf: (node) => `name:${node.id}`,
      ...overrides,
    })

  test('includes nodes that run before the Go to node (backward jump)', () => {
    expect(build().map((destination) => destination.value)).toContain(
      before.service.id
    )
  })

  test('includes nodes that run after the Go to node (forward jump)', () => {
    expect(build().map((destination) => destination.value)).toContain(
      after.service.id
    )
  })

  test('excludes the Go to node itself', () => {
    expect(build().map((destination) => destination.value)).not.toContain(
      goto.service.id
    )
  })

  test('excludes trigger nodes', () => {
    expect(build().map((destination) => destination.value)).not.toContain(
      trigger.service.id
    )
  })

  test('excludes nodes without a service yet', () => {
    // `pending` is on the goto's path but has no service, so it is not yet a
    // selectable destination.
    expect(build().map((destination) => destination.value)).not.toContain(
      undefined
    )
    expect(build()).toHaveLength(2)
  })

  test('maps each destination to its service id and resolved name', () => {
    expect(build()).toEqual([
      { value: before.service.id, name: `name:${before.id}` },
      { value: after.service.id, name: `name:${after.id}` },
    ])
  })
})
