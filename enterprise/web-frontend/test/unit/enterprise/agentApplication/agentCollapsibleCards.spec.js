import agentCollapsibleCards from '@baserow_enterprise/mixins/agentCollapsibleCards'

function section() {
  return { ...agentCollapsibleCards.data(), ...agentCollapsibleCards.methods }
}

describe('agent configuration cards folding', () => {
  test('a single item opens expanded', () => {
    const self = section()
    const items = [{ id: 1 }]
    expect(self.cardInitiallyExpanded(items[0], items)).toBe(true)
  })

  test('two or more items open folded, items added later expanded', () => {
    const self = section()
    const items = [{ id: 1 }, { id: 2 }]
    expect(self.cardInitiallyExpanded(items[0], items)).toBe(false)
    expect(self.cardInitiallyExpanded(items[1], items)).toBe(false)
    const added = { id: 3 }
    expect(self.cardInitiallyExpanded(added, [...items, added])).toBe(true)
  })

  test('items loaded after an empty start follow the same rule', () => {
    const self = section()
    expect(self.initialCardIds).toBeNull()
    const items = [{ id: 1 }, { id: 2 }, { id: 3 }]
    expect(self.cardInitiallyExpanded(items[2], items)).toBe(false)
  })
})
