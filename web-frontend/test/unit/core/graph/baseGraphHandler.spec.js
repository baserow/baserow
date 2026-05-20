import BaseGraphHandler from '@baserow/modules/core/graph/baseGraphHandler'

// Minimal concrete subclass for testing.
class TestHandler extends BaseGraphHandler {
  getPointMap() {
    return this.container.pointMap
  }
}

const pt = (id) => ({ id })

const make = (graph, points = {}) =>
  new TestHandler({
    graph: JSON.parse(JSON.stringify(graph)),
    pointMap: points,
  })

// Build a pointMap from an array of point objects.
const pm = (...ids) => Object.fromEntries(ids.map((id) => [id, pt(id)]))

describe('BaseGraphHandler', () => {
  describe('getPointMap abstraction', () => {
    test('throws if not implemented', () => {
      const h = new BaseGraphHandler({ graph: {} })
      expect(() => h.getPointMap()).toThrow('getPointMap')
    })
  })

  describe('getInfo', () => {
    test('returns info by numeric id', () => {
      const h = make({ 1: { next: { '': [2] } } })
      expect(h.getInfo(pt(1))).toEqual({ next: { '': [2] } })
    })

    test('returns info by raw id', () => {
      const h = make({ 1: { next: { '': [] } } })
      expect(h.getInfo(1)).toEqual({ next: { '': [] } })
    })

    test('returns undefined for unknown id', () => {
      const h = make({})
      expect(h.getInfo(pt(99))).toBeUndefined()
    })

    test('returns undefined for null', () => {
      const h = make({})
      expect(h.getInfo(null)).toBeUndefined()
    })
  })

  describe('_getChildrenIds', () => {
    test('dict format', () => {
      const h = make({})
      expect(h._getChildrenIds({ children: { 0: [1, 2], 1: [3] } })).toEqual([
        1, 2, 3,
      ])
    })

    test('legacy array format', () => {
      const h = make({})
      expect(h._getChildrenIds({ children: [1, 2] })).toEqual([1, 2])
    })

    test('missing children', () => {
      const h = make({})
      expect(h._getChildrenIds({})).toEqual([])
      expect(h._getChildrenIds(null)).toEqual([])
    })
  })

  describe('_getChildrenAsDict', () => {
    test('passes through dict unchanged', () => {
      const h = make({})
      const dict = { 0: [1], 1: [2] }
      expect(h._getChildrenAsDict(dict)).toBe(dict)
    })

    test('upgrades legacy array to {"": [...]}', () => {
      const h = make({})
      expect(h._getChildrenAsDict([1, 2])).toEqual({ '': [1, 2] })
    })

    test('null / undefined returns {}', () => {
      const h = make({})
      expect(h._getChildrenAsDict(null)).toEqual({})
      expect(h._getChildrenAsDict(undefined)).toEqual({})
    })
  })

  describe('hasPoints / getFirstPoint', () => {
    test('empty graph', () => {
      const h = make({})
      expect(h.hasPoints()).toBe(false)
      expect(h.getFirstPoint()).toBeNull()
    })

    test('single root', () => {
      const h = make({ 0: 1 }, pm(1))
      expect(h.hasPoints()).toBe(true)
      expect(h.getFirstPoint()).toEqual(pt(1))
    })
  })

  describe('getChildren', () => {
    const graph = {
      0: 1,
      1: { children: { 0: [2], 1: [4] } },
      2: { next: { '': [3] } },
      3: {},
      4: {},
    }
    const points = pm(1, 2, 3, 4)

    test('followChains=false returns only heads', () => {
      const h = make(graph, points)
      const children = h.getChildren(pt(1))
      expect(children.map((p) => p.id).sort()).toEqual([2, 4])
    })

    test('followChains=true follows next chains', () => {
      const h = make(graph, points)
      const children = h.getChildren(pt(1), { followChains: true })
      expect(children.map((p) => p.id).sort()).toEqual([2, 3, 4])
    })

    test('slot filter', () => {
      const h = make(graph, points)
      const children = h.getChildren(pt(1), { slot: '0', followChains: true })
      expect(children.map((p) => p.id)).toEqual([2, 3])
    })

    test('empty children', () => {
      const h = make({ 0: 1, 1: {} }, pm(1))
      expect(h.getChildren(pt(1))).toEqual([])
    })

    test('legacy array children with followChains=false', () => {
      const h = make({ 0: 1, 1: { children: [2] }, 2: {} }, pm(1, 2))
      expect(h.getChildren(pt(1))).toEqual([pt(2)])
    })
  })

  describe('getPointAtPosition', () => {
    const graph = {
      0: 1,
      1: { next: { '': [2] }, children: { 0: [3] } },
      2: {},
      3: {},
    }
    const points = pm(1, 2, 3)

    test('south with null ref returns first point', () => {
      const h = make(graph, points)
      expect(h.getPointAtPosition(null, 'south', '')).toEqual(pt(1))
    })

    test('south returns next point', () => {
      const h = make(graph, points)
      expect(h.getPointAtPosition(pt(1), 'south', '')).toEqual(pt(2))
    })

    test('south returns null when no next', () => {
      const h = make(graph, points)
      expect(h.getPointAtPosition(pt(2), 'south', '')).toBeNull()
    })

    test('child returns first child in slot', () => {
      const h = make(graph, points)
      expect(h.getPointAtPosition(pt(1), 'child', '0')).toEqual(pt(3))
    })

    test('child returns null for empty slot', () => {
      const h = make(graph, points)
      expect(h.getPointAtPosition(pt(1), 'child', '1')).toBeNull()
    })

    test('throws on unknown position', () => {
      const h = make(graph, points)
      expect(() => h.getPointAtPosition(pt(1), 'west', '')).toThrow()
    })
  })

  describe('getPointPosition', () => {
    test('root returns [null, south, ""]', () => {
      const h = make({ 0: 1, 1: {} }, pm(1))
      expect(h.getPointPosition(pt(1))).toEqual([null, 'south', ''])
    })

    test('south returns [predecessor, south, output]', () => {
      const h = make({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, pm(1, 2))
      expect(h.getPointPosition(pt(2))).toEqual([pt(1), 'south', ''])
    })

    test('child returns [parent, child, slot]', () => {
      const h = make({ 0: 1, 1: { children: { 0: [2] } }, 2: {} }, pm(1, 2))
      expect(h.getPointPosition(pt(2))).toEqual([pt(1), 'child', '0'])
    })

    test('child with legacy array returns [parent, child, ""]', () => {
      const h = make({ 0: 1, 1: { children: [2] }, 2: {} }, pm(1, 2))
      expect(h.getPointPosition(pt(2))).toEqual([pt(1), 'child', ''])
    })

    test('throws for unknown point', () => {
      const h = make({ 0: 1, 1: {} }, pm(1))
      expect(() => h.getPointPosition(pt(99))).toThrow()
    })
  })

  describe('getPreviousPositions', () => {
    test('returns path for shallow point', () => {
      const h = make({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, pm(1, 2))
      const path = h.getPreviousPositions(pt(2))
      expect(path).toHaveLength(1)
      expect(path[0]).toEqual([pt(1), 'south', ''])
    })

    test('returns path through nested child', () => {
      const h = make(
        { 0: 1, 1: { children: { 0: [2] } }, 2: { next: { '': [3] } }, 3: {} },
        pm(1, 2, 3)
      )
      const path = h.getPreviousPositions(pt(3))
      expect(path).toHaveLength(2)
      expect(path[0]).toEqual([pt(1), 'child', '0'])
      expect(path[1]).toEqual([pt(2), 'south', ''])
    })

    test('returns [] when target not reachable', () => {
      const h = make({ 0: 1, 1: {} }, pm(1))
      expect(h.getPreviousPositions(pt(99))).toEqual([])
    })
  })

  describe('insert', () => {
    test('as root into empty graph', () => {
      const h = make({}, pm(1))
      h.insert(pt(1), null, 'south', '')
      expect(h.graph['0']).toBe(1)
      expect(h.graph[1]).toEqual({})
    })

    test('as root displaces existing root', () => {
      const h = make({ 0: 2, 2: {} }, pm(1, 2))
      h.insert(pt(1), null, 'south', '')
      expect(h.graph['0']).toBe(1)
      expect(h.graph[1]).toEqual({ next: { '': [2] } })
    })

    test('south appends after reference', () => {
      const h = make({ 0: 1, 1: { next: { '': [3] } }, 3: {} }, pm(1, 2, 3))
      h.insert(pt(2), pt(1), 'south', '')
      expect(h.graph[1].next['']).toEqual([2])
      expect(h.graph[2]).toEqual({ next: { '': [3] } })
    })

    test('child inserts into slot', () => {
      const h = make({ 0: 1, 1: {} }, pm(1, 2))
      h.insert(pt(2), pt(1), 'child', '0')
      expect(h.graph[1].children['0']).toEqual([2])
      expect(h.graph[2]).toEqual({ next: { '': [] } })
    })

    test('north inserts before reference', () => {
      const h = make({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, pm(1, 2, 3))
      h.insert(pt(3), pt(2), 'north', '')
      expect(h.graph[1].next['']).toEqual([3])
      expect(h.graph[3]).toEqual({ next: { '': [2] } })
    })
  })

  describe('remove', () => {
    test('removes the only root element', () => {
      const h = make({ 0: 1, 1: {} }, pm(1))
      h.remove(pt(1))
      expect(h.graph['0']).toBeUndefined()
      expect(h.graph[1]).toBeUndefined()
    })

    test('removes root and promotes successor', () => {
      const h = make({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, pm(1, 2))
      h.remove(pt(1))
      expect(h.graph['0']).toBe(2)
      expect(h.graph[1]).toBeUndefined()
    })

    test('removes south element and stitches chain', () => {
      const h = make(
        { 0: 1, 1: { next: { '': [2] } }, 2: { next: { '': [3] } }, 3: {} },
        pm(1, 2, 3)
      )
      h.remove(pt(2))
      expect(h.graph[1].next['']).toEqual([3])
      expect(h.graph[2]).toBeUndefined()
    })

    test('removes child element and stitches slot', () => {
      const h = make(
        {
          0: 1,
          1: { children: { 0: [2] } },
          2: { next: { '': [3] } },
          3: {},
        },
        pm(1, 2, 3)
      )
      h.remove(pt(2))
      expect(h.graph[1].children['0']).toEqual([3])
      expect(h.graph[2]).toBeUndefined()
    })

    test('removes child with legacy array children', () => {
      const h = make({ 0: 1, 1: { children: [2] }, 2: {} }, pm(1, 2))
      h.remove(pt(2))
      expect(h.graph[1].children['']).toEqual([])
    })

    test('cascades deletion to children and their next-chain (default keepDescendants=false)', () => {
      // Container pt(1) has child pt(2); pt(3) follows pt(2) in the same slot.
      // pt(4) follows pt(1) as a sibling. Removing pt(1) must delete 1, 2, 3
      // but preserve pt(4) (a sibling, not a descendant).
      const h = make(
        {
          0: 1,
          1: { next: { '': [4] }, children: { '': [2] } },
          2: { next: { '': [3] } },
          3: {},
          4: {},
        },
        pm(1, 2, 3, 4)
      )
      h.remove(pt(1))
      expect(h.graph[1]).toBeUndefined()
      expect(h.graph[2]).toBeUndefined()
      expect(h.graph[3]).toBeUndefined()
      expect(h.graph['0']).toBe(4)
      expect(h.graph[4]).toBeDefined()
    })

    test('keepDescendants=true preserves children entries', () => {
      const h = make(
        {
          0: 1,
          1: { next: { '': [2] }, children: { '': [3] } },
          2: {},
          3: {},
        },
        pm(1, 2, 3)
      )
      h.remove(pt(1), { keepDescendants: true })
      expect(h.graph[1]).toBeUndefined()
      // pt(3) is a child — its entry must survive.
      expect(h.graph[3]).toBeDefined()
    })
  })

  describe('move', () => {
    test('moves point and preserves its children', () => {
      const h = make(
        {
          0: 1,
          1: { next: { '': [2] }, children: { 0: [3] } },
          2: {},
          3: {},
        },
        pm(1, 2, 3)
      )
      // Move pt(1) to south of pt(2)
      h.move(pt(1), pt(2), 'south', '')
      expect(h.graph['0']).toBe(2)
      expect(h.graph[2].next['']).toEqual([1])
      // Children of the moved point must be preserved
      expect(h.graph[1].children).toEqual({ 0: [3] })
    })

    test('null reference + south appends to end of chain', () => {
      // pt(1) -> pt(2) -> pt(3); move pt(1) to last position
      const h = make(
        { 0: 1, 1: { next: { '': [2] } }, 2: { next: { '': [3] } }, 3: {} },
        pm(1, 2, 3)
      )
      h.move(pt(1), null, 'south', '')
      expect(h.graph['0']).toBe(2)
      expect(h.graph[2].next['']).toEqual([3])
      expect(h.graph[3].next['']).toEqual([1])
      // pt(1) is now last: its next chain is empty
      expect(h.graph[1].next?.['']).toEqual([])
    })
  })

  describe('replace', () => {
    test('swaps point keeping graph structure', () => {
      const h = make({ 0: 1, 1: { next: { '': [2] } }, 2: {} }, pm(1, 2, 99))
      h.replace(pt(1), pt(99))
      expect(h.graph['0']).toBe(99)
      expect(h.graph[99]).toEqual({ next: { '': [2] } })
      expect(h.graph[1]).toBeUndefined()
    })
  })
})
