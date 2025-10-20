import { clone } from '@baserow/modules/core/utils/object'

const replace = (array, itemToReplace, replacement) => {
  const foundIndex = array.findIndex((item) => item === itemToReplace)
  return [
    ...array.slice(0, foundIndex),
    ...(Array.isArray(replacement) ? replacement : [replacement]),
    ...array.slice(foundIndex + 1),
  ]
}

export default class NodeGraphHandler {
  constructor(workflow) {
    this.graph = clone(workflow.graph)
    this.nodeMap = workflow.nodeMap
  }

  getNode(nodeId) {
    return this.nodeMap[nodeId]
  }

  getInfo(node) {
    if (node.id) {
      return this.graph[node.id]
    }
    return this.graph[node]
  }

  hasNodes() {
    return Boolean(this.getFirstNode())
  }

  getFirstNode() {
    if (this.graph['0']) {
      return this.getNode(this.graph['0'])
    }
    return null
  }

  getChildren(targetNode) {
    return (this.getInfo(targetNode)?.child || [])
      .map((id) => this.getNode(id))
      .filter((node) => node)
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
    }
    return []
  }

  getNodeAtPosition(positionNode, position, output) {
    output = String(output)

    let nextNodes

    switch (position) {
      case 'south':
        // First node
        if (positionNode === null) {
          return this.getNode(this.graph['0'])
        }

        nextNodes = this.getInfo(positionNode)?.next?.[output] || []
        if (nextNodes.length > 0) {
          return this.getNode(nextNodes[0])
        }
        break

      case 'child':
        nextNodes = this.getInfo(positionNode)?.child || []
        if (nextNodes.length > 0) {
          return this.getNode(nextNodes[0])
        }
        break

      default:
        throw new Error('Unexpected position')
    }
    return null
  }

  getPreviousPositions(targetNode) {
    const explore = (currentPosition, path) => {
      const node = this.getNodeAtPosition(...currentPosition)
      const nodeId = String(node.id)

      if (nodeId === String(targetNode.id)) {
        return path
      }

      const nodeInfo = this.getInfo(nodeId)

      const nextPositions = []
      // Collect all possible positions
      if (nodeInfo.next) {
        for (const uid of Object.keys(nodeInfo.next)) {
          if (nodeInfo.next[uid]?.length) {
            nextPositions.push([nodeId, 'south', uid])
          }
        }
      }

      if (nodeInfo.child?.length) {
        nextPositions.push([nodeId, 'child', ''])
      }

      for (const nextPosition of nextPositions) {
        const found = explore(nextPosition, [...path, nextPosition])
        if (found !== null && found !== undefined) {
          return found
        }
      }

      return null
    }

    const result = explore([null, 'south', ''], [])
    return result.map(([nid, p, o]) => [this.getNode(nid), p, o])
  }

  getNodePosition(node) {
    if (this.graph['0'] === node.id) {
      return [null, 'south', '']
    }
    for (const [nodeId, value] of Object.entries(this.graph)) {
      if (value.next) {
        const outputFound = Object.entries(value.next).find(([, nextOnEdge]) =>
          nextOnEdge.includes(node.id)
        )
        if (outputFound) {
          const previousNode = this.getNode(nodeId)
          return [previousNode, 'south', outputFound[0]]
        }
      }
      if (value.child) {
        if (value.child.includes(node.id)) {
          const parentNode = this.getNode(nodeId)
          return [parentNode, 'child', '']
        }
      }
    }
    throw new Error('Node not found in graph')
  }

  insert(node, positionNode, position, output) {
    if (!positionNode) {
      // We are creating the trigger
      let next = null
      if (this.graph['0']) {
        next = [this.graph['0']]
      }
      this.graph['0'] = node.id
      this.graph[node.id] = next ? { next: { '': next } } : {}
    } else {
      let newNodeNext
      switch (position) {
        case 'south':
          if (!this.graph[positionNode.id].next) {
            this.graph[positionNode.id].next = {}
          }
          if (!this.graph[positionNode.id].next[output]) {
            this.graph[positionNode.id].next[output] = []
          }

          newNodeNext = this.graph[positionNode.id].next[output]
          this.graph[positionNode.id].next[output] = [node.id]

          break
        case 'child':
          if (!this.graph[positionNode.id].child) {
            this.graph[positionNode.id].child = []
          }
          newNodeNext = this.graph[positionNode.id].child
          this.graph[positionNode.id].child = [node.id]

          break
        default:
          throw new Error('Unexpected position')
      }
      this.graph[node.id] = {
        next: { '': newNodeNext },
      }
    }
  }

  remove(node) {
    const [previousPositionNode, position, output] = this.getNodePosition(node)

    const nodeInfo = this.graph[node.id]
    const previousPositionNodeInfo = previousPositionNode
      ? this.graph[previousPositionNode.id]
      : null

    switch (position) {
      case 'south':
        if (previousPositionNodeInfo) {
          // We move next nodes of removed node to the previous node
          previousPositionNodeInfo.next[output] = replace(
            previousPositionNodeInfo.next[output],
            node.id,
            Object.values(nodeInfo.next || {}).flat()
          )
        }
        // Trigger node
        else if (this.graph[node.id].next && this.graph[node.id].next['']) {
          const next = this.graph[node.id].next[''][0]
          this.graph['0'] = next
        } else {
          delete this.graph['0']
        }
        break
      case 'child':
        previousPositionNodeInfo.child = replace(
          previousPositionNodeInfo.child,
          node.id,
          Object.values(nodeInfo.next || {}).flat()
        )
        break
      default:
        throw new Error('Unexpected position')
    }

    delete this.graph[node.id]
  }

  move(nodeToMove, positionNode, position, output) {
    const previousChild = this.graph[nodeToMove.id].child

    this.remove(nodeToMove)
    this.insert(nodeToMove, positionNode, position, output)

    this.graph[nodeToMove.id].child = previousChild
  }

  replace(nodeToReplace, newNode) {
    const [positionNode, position, output] = this.getNodePosition(nodeToReplace)

    this.remove(nodeToReplace)
    this.insert(newNode, positionNode, position, output)
  }
}
