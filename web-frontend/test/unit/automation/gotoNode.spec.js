import { isValidGotoDestination } from '@baserow/modules/automation/utils/gotoNode'

describe('isValidGotoDestination', () => {
  // A linear workflow: trigger -> before -> goto -> after, all at root level.
  const trigger = { id: 1, type: 'trigger' }
  const before = { id: 2, type: 'create_row' }
  const goto = { id: 3, type: 'goto_node' }
  const after = { id: 4, type: 'create_row' }

  const isTrigger = (node) => node.type === 'trigger'
  const noAncestors = () => []
  // Everything except `after` runs before the goto node.
  const previousNodesOf = () => [trigger, before]

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

  test('rejects a node that runs after (forward jump)', () => {
    expect(validate(after)).toBe(false)
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
})
