import AutomationWorkflowNodeService from '@baserow/modules/automation/services/automationWorkflowNode'

const state = {
  nodes: [],
}

const mutations = {
  SET_ITEMS(state, { nodes }) {
    state.nodes = nodes
  },
  ADD_ITEM(state, { node }) {
    state.nodes.push(node)
  },
  UPDATE_ITEM(state, { node, values }) {
    const index = state.nodes.findIndex((item) => item.id === node.id)
    if (index !== -1) {
      Object.assign(state.nodes[index], values)
    }
  },
  DELETE_ITEM(state, { nodeId }) {
    const index = state.nodes.findIndex((item) => item.id === nodeId)
    if (index !== -1) {
      state.nodes.splice(index, 1)
    }
  },
  ORDER_ITEMS(state, { order }) {
    state.nodes.forEach((node) => {
      const index = order.findIndex((value) => value === node.id)
      node.order = index === -1 ? 0 : index + 1 // Assuming nodes have an 'order' property
    })
    // Optionally re-sort the local array based on the new order
    state.nodes.sort((a, b) => a.order - b.order)
  },
}

const actions = {
  async fetch({ commit }, { workflowId }) {
    const { data: nodes } = await AutomationWorkflowNodeService(
      this.$client
    ).get(workflowId)
    commit('SET_ITEMS', { nodes })
    return nodes
  },
  async create({ commit }, { workflowId, type }) {
    const { data: node } = await AutomationWorkflowNodeService(
      this.$client
    ).create(workflowId, type)
    commit('ADD_ITEM', { node })
    return node
  },
  async update({ commit }, { node, values }) {
    const { data: updatedNodeData } = await AutomationWorkflowNodeService(
      this.$client
    ).update(node.id, values)
    // Ensure only the updated values are committed
    const updatePayload = Object.keys(values).reduce((result, key) => {
      result[key] = updatedNodeData[key]
      return result
    }, {})
    commit('UPDATE_ITEM', { node, values: updatePayload })
    return updatedNodeData
  },
  async delete({ commit }, { nodeId }) {
    await AutomationWorkflowNodeService(this.$client).delete(nodeId)
    commit('DELETE_ITEM', { nodeId })
  },
  async order({ commit, state }, { workflowId, order, oldOrder }) {
    commit('ORDER_ITEMS', { order })
    try {
      await AutomationWorkflowNodeService(this.$client).order(workflowId, order)
    } catch (error) {
      // Revert to the old order if the API call fails
      commit('ORDER_ITEMS', { order: oldOrder })
      throw error
    }
  },
}

const getters = {
  getAll(state) {
    // Return a sorted copy based on the order property
    return [...state.nodes].sort((a, b) => a.order - b.order)
  },
  findById: (state) => (nodeId) => {
    return state.nodes.find((node) => node.id === nodeId)
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
