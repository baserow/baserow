const getOrder = (nodeId, adjacencyList, visited) => {
  if (visited.has(nodeId)) {
    return []
  }
  visited.add(nodeId)
  const children = adjacencyList[nodeId] || []
  const childOrders = children.flatMap((childId) =>
    getOrder(childId, adjacencyList, visited)
  )
  return [nodeId, ...childOrders]
}

export const topologicalSort = (nodes) => {
  const adjacencyList = {}
  let rootNodeId = null
  nodes.forEach((node) => {
    if (node.previous_node_id === null) {
      rootNodeId = node.id
    } else {
      if (!adjacencyList[node.previous_node_id]) {
        adjacencyList[node.previous_node_id] = []
      }
      adjacencyList[node.previous_node_id].push(node.id)
    }
  })

  if (rootNodeId === null) {
    // This can happen if the nodes list is empty for example.
    return []
  }

  const visited = new Set()
  const sortedOrder = getOrder(rootNodeId, adjacencyList, visited)
  return sortedOrder
}
