/**
 * Pure helpers for the "Go to node" connector markers shown in the workflow
 * editor. Instead of drawing a line between a Go to node and its destination,
 * both ends are tagged with a matching marker (a letter) so the reader can pair
 * them by eye — far clearer than long lines criss-crossing the canvas.
 */

/**
 * Maps a zero-based jump index to its marker label. The first 26 jumps are
 * lettered A–Z; once those run out the alphabet repeats with an incrementing
 * numeric suffix: A1, B1, …, Z1, A2, … This keeps every marker short while
 * staying unique for arbitrarily many jumps.
 *
 * @param {number} index - Zero-based position of the jump.
 * @returns {string} The marker label, e.g. "A", "Z", "A1".
 */
export function markerLabel(index) {
  const letter = String.fromCharCode(65 + (index % 26))
  const cycle = Math.floor(index / 26)
  return cycle === 0 ? letter : `${letter}${cycle}`
}

/**
 * Walks the workflow nodes in order and assigns a stable marker to every valid
 * jump a node declares (see `NodeType.getConnections`). Ordering follows the
 * node order, so labels stay stable as long as the graph does.
 *
 * @param {Object} params
 * @param {Array} params.nodes - Nodes in the order markers should be assigned.
 * @param {(node: Object) => Array<{destinationNodeId: number}>}
 *   params.getConnectionsFor - Returns the connections a node wants drawn.
 * @returns {Array<{sourceId: number, destinationId: number, marker: string}>}
 */
export function assignGotoMarkers({ nodes, getConnectionsFor }) {
  const jumps = []
  for (const node of nodes) {
    for (const { destinationNodeId } of getConnectionsFor(node)) {
      jumps.push({
        sourceId: node.id,
        destinationId: destinationNodeId,
        marker: markerLabel(jumps.length),
      })
    }
  }
  return jumps
}
