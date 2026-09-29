import {
  markerLabel,
  assignGotoMarkers,
} from '@baserow/modules/automation/utils/gotoMarkers'

describe('markerLabel', () => {
  test('the first 26 jumps are lettered A–Z', () => {
    expect(markerLabel(0)).toBe('A')
    expect(markerLabel(1)).toBe('B')
    expect(markerLabel(25)).toBe('Z')
  })

  test('once the alphabet runs out the suffix increments: A1, B1, … A2', () => {
    expect(markerLabel(26)).toBe('A1')
    expect(markerLabel(27)).toBe('B1')
    expect(markerLabel(51)).toBe('Z1')
    expect(markerLabel(52)).toBe('A2')
  })
})

describe('assignGotoMarkers', () => {
  const connectionsByNode = {
    1: [{ destinationNodeId: 10 }],
    2: [{ destinationNodeId: 20 }],
  }
  const getConnectionsFor = (node) => connectionsByNode[node.id] || []

  test('assigns markers in node order', () => {
    const jumps = assignGotoMarkers({
      nodes: [{ id: 1 }, { id: 2 }, { id: 3 }],
      getConnectionsFor,
    })
    expect(jumps).toEqual([
      { sourceId: 1, destinationId: 10, marker: 'A' },
      { sourceId: 2, destinationId: 20, marker: 'B' },
    ])
  })

  test('nodes without connections are skipped without consuming a marker', () => {
    const jumps = assignGotoMarkers({
      nodes: [{ id: 3 }, { id: 1 }],
      getConnectionsFor,
    })
    // Node 3 has no connections, so node 1's jump still gets the first marker.
    expect(jumps).toEqual([{ sourceId: 1, destinationId: 10, marker: 'A' }])
  })

  test('a node may declare multiple jumps, each getting its own marker', () => {
    const jumps = assignGotoMarkers({
      nodes: [{ id: 1 }],
      getConnectionsFor: () => [
        { destinationNodeId: 10 },
        { destinationNodeId: 20 },
      ],
    })
    expect(jumps.map((j) => j.marker)).toEqual(['A', 'B'])
  })
})
