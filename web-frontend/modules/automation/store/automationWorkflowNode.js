import AutomationWorkflowNodeService from '@baserow/modules/automation/services/automationWorkflowNode'

const state = {}

const updateCachedValues = (workflow) => {
  if (!workflow || !workflow.nodes) return

  workflow.nodeMap = Object.fromEntries(
    workflow.nodes.map((node) => [`${node.id}`, node])
  )
}

const mutations = {
  SET_ITEMS(state, { workflow, nodes }) {
    workflow.nodes = nodes || []
    updateCachedValues(workflow)
  },
  ADD_ITEM(state, { workflow, node }) {
    workflow.nodes.push(node)
    updateCachedValues(workflow)
  },
  UPDATE_ITEM(state, { workflow, node, values }) {
    const index = workflow.nodes.findIndex((item) => item.id === node.id)
    if (index !== -1) {
      Object.assign(workflow.nodes[index], values)
    }
    updateCachedValues(workflow)
  },
  DELETE_ITEM(state, { workflow, nodeId }) {
    const nodeIdStr = nodeId.toString()
    workflow.nodes = workflow.nodes.filter(
      (item) => item.id.toString() !== nodeIdStr
    )
    updateCachedValues(workflow)
  },
  ORDER_ITEMS(state, { workflow, order }) {
    const updatedNodes = [...workflow.nodes]
    updatedNodes.forEach((node) => {
      const index = order.findIndex((value) => value === node.id)
      node.order = index === -1 ? 0 : index + 1
    })
    updatedNodes.sort((a, b) => a.order - b.order)
    workflow.nodes = updatedNodes
    updateCachedValues(workflow)
  },
  ADD_ITEM_AT(state, { workflow, node, index }) {
    workflow.nodes.splice(index, 0, node)
    updateCachedValues(workflow)
  },
}

const actions = {
  async fetch({ commit }, { workflow }) {
    if (!workflow) return []

    const { data: nodes } = await AutomationWorkflowNodeService(
      this.$client
    ).get(workflow.id)

    if (!workflow.nodes) {
      workflow.nodes = []
    }

    commit('SET_ITEMS', { workflow, nodes })
    return nodes
  },
  async create({ commit, getters }, { workflow, type, previousNodeId = null }) {
    // Create a temporary node with a unique temporary ID
    const tempId = `temp-${Date.now()}-${Math.floor(Math.random() * 1000)}`

    // Get existing nodes
    const existingNodes = getters.getNodes(workflow)

    // Calculate position
    let tempOrder
    let nodeIndex

    if (previousNodeId === null) {
      // Add at the beginning
      tempOrder = existingNodes.length > 0 ? existingNodes[0].order - 1 : 1
      nodeIndex = 0
    } else {
      // Find the previous node
      const prevNodeIndex = existingNodes.findIndex(
        (n) => n.id.toString() === previousNodeId.toString()
      )

      if (prevNodeIndex === -1) {
        // Previous node not found, add at the end
        tempOrder = existingNodes.length + 1
        nodeIndex = existingNodes.length
      } else {
        // Add after the specified node
        const prevNode = existingNodes[prevNodeIndex]
        const nextNode = existingNodes[prevNodeIndex + 1]

        // Calculate order between prev and next nodes or after prev if it's the last
        tempOrder = nextNode
          ? prevNode.order + (nextNode.order - prevNode.order) / 2
          : prevNode.order + 1

        nodeIndex = prevNodeIndex + 1
      }
    }

    // Create the temporary node
    const tempNode = {
      id: tempId,
      type,
      workflow_id: workflow.id,
      order: tempOrder,
    }

    // Apply optimistic create with position
    commit('ADD_ITEM_AT', { workflow, node: tempNode, index: nodeIndex })

    try {
      // Send API request
      const { data: node } = await AutomationWorkflowNodeService(
        this.$client
      ).create(workflow.id, type)

      // Calculate the final order for server
      const nodesWithoutTemp = getters
        .getNodes(workflow)
        .filter((n) => n.id !== tempId)
        .map((n) => n.id)

      // Insert the real node ID at the same position as the temp node was
      const newFinalOrderIds = [...nodesWithoutTemp]
      newFinalOrderIds.splice(nodeIndex, 0, node.id)

      // Remove temp node and add real one
      commit('DELETE_ITEM', { workflow, nodeId: tempId })
      commit('ADD_ITEM', { workflow, node })

      // Order the nodes correctly
      commit('ORDER_ITEMS', { workflow, order: newFinalOrderIds })

      // Send the order to the server
      await AutomationWorkflowNodeService(this.$client).order(
        workflow.id,
        newFinalOrderIds
      )

      return node
    } catch (error) {
      // If API fails, remove the temporary node
      commit('DELETE_ITEM', { workflow, nodeId: tempId })
      throw error
    }
  },
  async update({ commit, getters }, { workflow, nodeId, values }) {
    const node = getters.findById(workflow, nodeId)
    const originalNode = { ...node }
    commit('UPDATE_ITEM', { workflow, node, values })

    try {
      const { data: updatedNodeData } = await AutomationWorkflowNodeService(
        this.$client
      ).update(node.id, values)

      const serverValues = Object.keys(values).reduce((result, key) => {
        result[key] = updatedNodeData[key]
        return result
      }, {})
      commit('UPDATE_ITEM', { workflow, node, values: serverValues })

      return updatedNodeData
    } catch (error) {
      const rollbackValues = {}
      Object.keys(values).forEach((key) => {
        rollbackValues[key] = originalNode[key]
      })
      commit('UPDATE_ITEM', { workflow, node, values: rollbackValues })
      throw error
    }
  },
  async delete({ commit, getters }, { workflow, nodeId }) {
    const node = getters.findById(workflow, nodeId)
    const originalNode = { ...node }
    commit('DELETE_ITEM', { workflow, nodeId })
    try {
      await AutomationWorkflowNodeService(this.$client).delete(nodeId)
    } catch (error) {
      commit('ADD_ITEM', { workflow, node: originalNode })
      throw error
    }
  },
  async order({ commit }, { workflow, order, oldOrder }) {
    commit('ORDER_ITEMS', { workflow, order })
    try {
      await AutomationWorkflowNodeService(this.$client).order(
        workflow.id,
        order
      )
    } catch (error) {
      commit('ORDER_ITEMS', { workflow, order: oldOrder })
      throw error
    }
  },
}

const getters = {
  getNodes: (state) => (workflow) => {
    if (!workflow) return []
    if (!workflow.nodes) workflow.nodes = []
    return workflow.nodes
  },
  findById: (state) => (workflow, nodeId) => {
    if (!workflow || !workflow.nodes) return null

    const nodeIdStr = nodeId.toString()
    if (workflow.nodeMap && workflow.nodeMap[nodeIdStr])
      return workflow.nodeMap[nodeIdStr]

    return null
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
