import BaseGraphHandler from '@baserow/modules/core/graph/baseGraphHandler'

export default class NodeGraphHandler extends BaseGraphHandler {
  constructor(workflow) {
    super(workflow)
  }

  getPointMap() {
    return this.container.nodeMap
  }

  getNode(nodeId) {
    return this.getPoint(nodeId)
  }

  hasNodes() {
    return this.hasPoints()
  }

  getFirstNode() {
    return this.getFirstPoint()
  }

  getNodeAtPosition(referenceNode, position, output) {
    return this.getPointAtPosition(referenceNode, position, output)
  }

  getNodePosition(node) {
    return this.getPointPosition(node)
  }

  // Returns only the head of each slot (no next-chain traversal).
  getChildren(targetNode) {
    return super.getChildren(targetNode)
  }

  getNextNodes(targetNode, output = null) {
    return this.getNextPoints(targetNode, output)
  }

  // Depth-first ordered flat list of all nodes, i.e. the order they're read in
  // top to bottom in the editor. `workflow.nodes` is ordered by id (creation
  // order) instead, so anything surfacing nodes as a list to the user (e.g. the
  // "Go to node" destination dropdown) should go through this.
  getOrderedNodes() {
    return this.getPointsInDepthFirstOrder({
      skipMissing: true,
      skipChildrenOfMissing: true,
    })
  }
}
