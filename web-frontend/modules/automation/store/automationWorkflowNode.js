import { uuid } from '@baserow/modules/core/utils/string'
import AutomationWorkflowNodeService from '@baserow/modules/automation/services/automationWorkflowNode'
import { NodeEditorSidePanelType } from '@baserow/modules/automation/editorSidePanelTypes'

const state = {}

const updateCachedValues = (workflow) => {
  if (!workflow || !workflow.nodes) return

  workflow.nodeMap = Object.fromEntries(
    workflow.nodes.map((node) => [`${node.id}`, node])
  )
}

export function populateNode(node) {
  return { ...node, _: { loading: false } }
}

const mutations = {
  SET_ITEMS(state, { workflow, nodes }) {
    workflow.nodes = nodes.map((node) => populateNode(node))
    workflow.selectedNode = null
    updateCachedValues(workflow)
  },
  ADD_ITEM(state, { workflow, node }) {
    workflow.nodes.push(populateNode(node))
    updateCachedValues(workflow)
  },
  UPDATE_ITEM(state, { workflow, node, values }) {
    const index = workflow.nodes.findIndex((item) => item.id === node.id)
    Object.assign(workflow.nodes[index], values)
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
    workflow.nodes.splice(index, 0, populateNode(node))
    updateCachedValues(workflow)
  },
  SELECT_ITEM(state, { workflow, node }) {
    workflow.selectedNode = node
  },
  SET_LOADING(state, { node, value }) {
    node._.loading = value
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
  async create(
    { commit, dispatch, getters },
    { workflow, type, previousNodeId = null }
  ) {
    // Get existing nodes to determine beforeId
    const existingNodes = getters.getNodes(workflow)

    let beforeId = null
    let nodeIndex = 0

    if (previousNodeId) {
      // Find the previous node and get the next one as beforeId
      const prevNodeIndex = existingNodes.findIndex(
        (n) => n.id.toString() === previousNodeId.toString()
      )

      if (prevNodeIndex === -1) {
        // Previous node not found, add at the end (beforeId = null)
        beforeId = null
        nodeIndex = existingNodes.length
      } else {
        // Add after the specified node
        const nextNode = existingNodes[prevNodeIndex + 1]
        beforeId = nextNode ? nextNode.id : null
        nodeIndex = prevNodeIndex + 1
      }
    } else if (existingNodes.length > 0) {
      // previousNodeId is null and there are existing nodes - add at the beginning
      beforeId = existingNodes[0].id
      nodeIndex = 0
    }

    // Create a temporary node for optimistic UI
    const tempId = uuid()
    const tempNode = {
      id: tempId,
      type,
      workflow_id: workflow.id,
    }

    // Apply optimistic create
    commit('ADD_ITEM_AT', { workflow, node: tempNode, index: nodeIndex })

    try {
      // Send API request with beforeId
      const { data: node } = await AutomationWorkflowNodeService(
        this.$client
      ).create(workflow.id, type, beforeId)

      // Remove temp node and add real one
      commit('DELETE_ITEM', { workflow, nodeId: tempId })
      commit('ADD_ITEM_AT', { workflow, node, index: nodeIndex })

      setTimeout(() => {
        const populatedNode = getters.findById(workflow, node.id)
        dispatch('select', { workflow, node: populatedNode })
      })

      return node
    } catch (error) {
      // If API fails, remove the temporary node
      commit('DELETE_ITEM', { workflow, nodeId: tempId })
      throw error
    }
  },
  forceUpdate({ commit, dispatch }, { workflow, node, values }) {
    commit('UPDATE_ITEM', { workflow, node, values })
  },
  async update({ commit, dispatch, getters }, { workflow, nodeId, values }) {
    const oldValues = {}
    const newValues = {}
    const node = getters.findById(workflow, nodeId)
    Object.keys(values).forEach((name) => {
      if (Object.prototype.hasOwnProperty.call(node, name)) {
        oldValues[name] = node[name]
        newValues[name] = values[name]
      }
    })

    await dispatch('forceUpdate', { workflow, node, values: newValues })

    commit('SET_LOADING', { node, value: true })
    try {
      const { data: updatedNode } = await AutomationWorkflowNodeService(
        this.$client
      ).update(node.id, newValues)
      await dispatch('forceUpdate', {
        workflow,
        node,
        values: updatedNode,
      })
    } catch (error) {
      commit('UPDATE_ITEM', { workflow, node, values: oldValues })
      throw error
    } finally {
      commit('SET_LOADING', { node, value: false })
    }
  },
  async delete({ commit, dispatch, getters }, { workflow, nodeId }) {
    const node = getters.findById(workflow, nodeId)
    const originalNode = { ...node }
    if (getters.getSelected(workflow)?.id === nodeId) {
      dispatch('select', { workflow, node: null })
    }
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
  select({ commit, dispatch }, { workflow, node }) {
    commit('SELECT_ITEM', { workflow, node })
    dispatch(
      'automationWorkflow/setActiveSidePanel',
      node ? NodeEditorSidePanelType.getType() : null,
      { root: true }
    )
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
  getSelected: (state) => (workflow) => {
    if (!workflow) return null
    return workflow.selectedNode
  },
  getLoading: (state) => (node) => {
    return node._.loading
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
