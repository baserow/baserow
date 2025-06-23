import { uuid } from '@baserow/modules/core/utils/string'
import AutomationWorkflowNodeService from '@baserow/modules/automation/services/automationWorkflowNode'
import { NodeEditorSidePanelType } from '@baserow/modules/automation/editorSidePanelTypes'

const state = {}

const updateContext = {
  updateTimeout: null,
  promiseResolve: null,
  lastUpdatedValues: null,
  valuesToUpdate: {},
}

const updateCachedValues = (workflow) => {
  if (!workflow || !workflow.nodes) return

  workflow.nodeMap = Object.fromEntries(
    workflow.nodes.map((node) => [`${node.id}`, node])
  )
  workflow.idMap = Object.fromEntries(
    workflow.nodes.map((node) => [`${node.id}`, uuid()])
  )
}

export function populateNode(node) {
  return { ...node, _: { loading: false } }
}

const mutations = {
  SET_ITEMS(state, { workflow, nodes }) {
    workflow.nodes = nodes.map((node) => populateNode(node))
    workflow.selectedNodeId = null
    updateCachedValues(workflow)
  },
  ADD_ITEM(state, { workflow, node }) {
    workflow.nodes.push(populateNode(node))
    updateCachedValues(workflow)
  },
  UPDATE_ITEM(
    state,
    {
      workflow,
      node: nodeToUpdate,
      assignSelectedNode,
      values,
      typeChanged = false,
    }
  ) {
    const index = workflow.nodes.findIndex(
      (node) => node.id === nodeToUpdate.id
    )
    if (index === -1) {
      // The node might have been deleted during the debounced update
      return
    }

    const newValue = typeChanged
      ? populateNode(values)
      : {
          ...workflow.nodes[index],
          ...values,
        }

    if (assignSelectedNode) {
      workflow.selectedNodeId = newValue.id
    }

    workflow.nodes.splice(index, 1, newValue)

    if (typeChanged) {
      // When a node's `type` changes, it will have a new `id` as it's effectively
      // a new node with some cloned values. We need to pluck out the existing flow ID
      // we have for the 'old' node, update the `idMap` cache, and then re-add that
      // flow ID using the 'new' node.
      const nodeFlowId = workflow.idMap[nodeToUpdate.id]
      updateCachedValues(workflow)
      delete workflow.idMap[nodeToUpdate.id]
      workflow.idMap[newValue.id] = nodeFlowId
    }
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
    workflow.selectedNodeId = node?.id || null
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
  forceUpdate(
    { commit, dispatch },
    { workflow, node, assignSelectedNode, values, typeChanged }
  ) {
    commit('UPDATE_ITEM', {
      workflow,
      node,
      assignSelectedNode,
      values,
      typeChanged,
    })
  },
  async updateDebounced(
    { dispatch, commit, getters },
    { workflow, node, values }
  ) {
    // These values should not be updated via a regular update request
    const excludeValues = ['order']

    const oldValues = {}
    Object.keys(values).forEach((name) => {
      if (
        Object.prototype.hasOwnProperty.call(node, name) &&
        !excludeValues.includes(name)
      ) {
        oldValues[name] = node[name]
        // Accumulate the changed values to send all the ongoing changes with the
        // final request.
        updateContext.valuesToUpdate[name] = structuredClone(values[name])
      }
    })

    let assignSelectedNode = false
    const nodeTypeChanging = values.type && node.type !== values.type
    if (nodeTypeChanging && getters.getSelected(workflow)?.id === node.id) {
      // If the node type is changing, and it's our currently selected node,
      // we need to ensure that after the update, the `workflow.selectedNodeId`
      // is updated, because a type changes causes the node ID to change too.
      assignSelectedNode = true
    }

    await dispatch('forceUpdate', {
      workflow,
      node,
      values: updateContext.valuesToUpdate,
    })

    return new Promise((resolve, reject) => {
      const fire = async () => {
        commit('SET_LOADING', { node, value: true })
        const toUpdate = updateContext.valuesToUpdate
        updateContext.valuesToUpdate = {}
        try {
          const { data } = await AutomationWorkflowNodeService(
            this.$client
          ).update(node.id, toUpdate)
          updateContext.lastUpdatedValues = null

          excludeValues.forEach((name) => {
            delete data[name]
          })

          await dispatch('forceUpdate', {
            workflow,
            node,
            assignSelectedNode,
            values: data,
            typeChanged: nodeTypeChanging,
          })

          resolve()
        } catch (error) {
          await dispatch('forceUpdate', {
            workflow,
            node,
            values: updateContext.lastUpdatedValues,
          })
          updateContext.lastUpdatedValues = null
          reject(error)
        }
        updateContext.lastUpdatedValues = null
        commit('SET_LOADING', { node, value: false })
      }

      if (updateContext.promiseResolve) {
        updateContext.promiseResolve()
        updateContext.promiseResolve = null
      }

      clearTimeout(updateContext.updateTimeout)

      if (!updateContext.lastUpdatedValues) {
        updateContext.lastUpdatedValues = oldValues
      }

      updateContext.updateTimeout = setTimeout(fire, 500)
      updateContext.promiseResolve = resolve
    })
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
    if (workflow.nodeMap && workflow.nodeMap[nodeIdStr]) {
      return workflow.nodeMap[nodeIdStr]
    }
    return null
  },
  getSelected: (state) => (workflow) => {
    if (!workflow) return null
    return workflow.nodeMap?.[workflow.selectedNodeId] || null
  },
  getLoading: (state) => (node) => {
    return node._.loading
  },
  getFlowId: (state) => (workflow, nodeId) => {
    return workflow.idMap[nodeId]
  },
  getNodeIdFromFlowId: (state) => (workflow, flowId) => {
    return Object.keys(workflow.idMap).find(
      (nodeId) => workflow.idMap[nodeId] === flowId
    )
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
