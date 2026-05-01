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
    if (this.getInfo(targetNode)?.next) {
      return Object.entries(this.getInfo(targetNode).next)
        .filter(
          ([uid, nodes]) => nodes.length && (output === null || uid === output)
        )
        .map(([, nodes]) => nodes)
        .flat()
        .map((id) => this.getNode(id))
        .filter((node) => node)
    }
    return []
  }
}
