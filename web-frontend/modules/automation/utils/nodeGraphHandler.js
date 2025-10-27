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
    return this.nodeMap[nodeId] || null
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
    return (this.getInfo(targetNode)?.children || [])
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
        .filter((node) => node)
    }
    return []
  }

  getNodeAtPosition(referenceNode, position, output) {
    output = String(output)

    let nextNodes

    switch (position) {
      case 'south':
        // First node
        if (referenceNode === null) {
          return this.getNode(this.graph['0'])
        }

        nextNodes = this.getInfo(referenceNode)?.next?.[output] || []
        if (nextNodes.length > 0) {
          return this.getNode(nextNodes[0])
        }
        break

      case 'child':
        nextNodes = this.getInfo(referenceNode)?.children || []
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

      if (node === null) {
        return null
      }

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

      if (nodeInfo.children?.length) {
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
    if (!result) {
      return []
    }
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
      if (value.children) {
        if (value.children.includes(node.id)) {
          const parentNode = this.getNode(nodeId)
          return [parentNode, 'child', '']
        }
      }
    }
    throw new Error('Node not found in graph')
  }

  insert(node, referenceNode, position, output) {
    if (!referenceNode) {
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
          if (!this.graph[referenceNode.id].next) {
            this.graph[referenceNode.id].next = {}
          }
          if (!this.graph[referenceNode.id].next[output]) {
            this.graph[referenceNode.id].next[output] = []
          }

          newNodeNext = this.graph[referenceNode.id].next[output]
          this.graph[referenceNode.id].next[output] = [node.id]

          break
        case 'child':
          if (!this.graph[referenceNode.id].children) {
            this.graph[referenceNode.id].children = []
          }
          newNodeNext = this.graph[referenceNode.id].children
          this.graph[referenceNode.id].children = [node.id]

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
    const [previousReferenceNode, position, output] = this.getNodePosition(node)

    const nodeInfo = this.graph[node.id]
    const previousReferenceNodeInfo = previousReferenceNode
      ? this.graph[previousReferenceNode.id]
      : null

    switch (position) {
      case 'south':
        if (previousReferenceNodeInfo) {
          // We move next nodes of removed node to the previous node
          previousReferenceNodeInfo.next[output] = replace(
            previousReferenceNodeInfo.next[output],
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
        previousReferenceNodeInfo.children = replace(
          previousReferenceNodeInfo.children,
          node.id,
          Object.values(nodeInfo.next || {}).flat()
        )
        break
      default:
        throw new Error('Unexpected position')
    }

    delete this.graph[node.id]
  }

  move(nodeToMove, referenceNode, position, output) {
    const previousChildren = this.graph[nodeToMove.id].children

    this.remove(nodeToMove)
    this.insert(nodeToMove, referenceNode, position, output)

    this.graph[nodeToMove.id].children = previousChildren
  }

  replace(nodeToReplace, newNode) {
    const [referenceNode, position, output] =
      this.getNodePosition(nodeToReplace)

    this.remove(nodeToReplace)
    this.insert(newNode, referenceNode, position, output)
  }
}
