import { uuid } from '@baserow/modules/core/utils/string'
import AutomationWorkflowNodeService from '@baserow/modules/automation/services/automationWorkflowNode'
import { NodeEditorSidePanelType } from '@baserow/modules/automation/editorSidePanelTypes'

const state = {
  selectedNodeId: null,
}

const updateContext = {
  updateTimeout: null,
  promiseResolve: null,
  lastUpdatedValues: null,
  valuesToUpdate: {},
}

const updateCachedValues = (workflow) => {
  if (!workflow || !workflow.nodes) return

  workflow.orderedNodes = workflow.nodes.sort((a, b) => a.order - b.order)
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
    workflow.selectedNodeId = null
    updateCachedValues(workflow)
  },
  ADD_ITEM(state, { workflow, node }) {
    workflow.nodes.push(populateNode(node))
    updateCachedValues(workflow)
  },
  UPDATE_ITEM(
    state,
    { workflow, node: nodeToUpdate, values, override = false }
  ) {
    workflow.nodes.forEach((node) => {
      if (node.id === nodeToUpdate.id) {
        const newValue = override
          ? populateNode(values)
          : {
              ...node,
              ...values,
            }
        Object.assign(node, newValue)
      }
    })
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
  SELECT_ITEM(state, { workflow, node }) {
    workflow.selectedNodeId = node?.id || null
  },
  SET_LOADING(state, { node, value }) {
    node._.loading = value
  },
}

const actions = {
  forceCreate({ commit, getters, dispatch }, { workflow, node }) {
    if (!workflow) return

    const previousNode = getters.findById(workflow, node.previous_node_id)
    const nextNodes = getters.getNextNodes(
      workflow,
      previousNode,
      node.previous_node_output
    )

    const beforeNode = nextNodes.length > 0 ? nextNodes[0] : null
    // Add the new node into the workflow
    commit('ADD_ITEM', { workflow, node })

    if (beforeNode) {
      commit('UPDATE_ITEM', {
        workflow,
        node: beforeNode,
        values: { previous_node_id: node.id, previous_node_output: '' },
      })
    }
  },
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
    { workflow, type, previousNodeId = null, previousNodeOutput = null }
  ) {
    // Using the `previousNodeId` and `previousNodeOutput` to determine
    // what the `beforeId` should be. We will have `beforeId` if we're
    // creating a node after `previousNodeId`, and `previousNodeId` has
    // a node that follows it.
    const nodeType = this.$registry.get('node', type)
    const previousNode = getters.findById(workflow, previousNodeId)
    const nextNodes = getters.getNextNodes(
      workflow,
      previousNode,
      previousNodeOutput
    )

    const beforeNode = nextNodes.length > 0 ? nextNodes[0] : null
    const beforeId = beforeNode?.id || null
    const beforeOldValues = beforeNode
      ? {
          previous_node_id: beforeNode.previous_node_id,
          previous_node_output: beforeNode.previous_node_output,
        }
      : {}

    // Apply optimistic create
    const tempNode = nodeType.getDefaultValues({
      id: uuid(),
      type,
      previous_node_id: previousNodeId,
      previous_node_output: previousNodeOutput,
      workflow: workflow.id,
    })
    commit('ADD_ITEM', { workflow, node: tempNode })

    // Apply optimistic beforeNode update.
    if (beforeNode) {
      commit('UPDATE_ITEM', {
        workflow,
        node: beforeNode,
        values: { previous_node_id: tempNode.id, previous_node_output: '' },
      })
    }

    try {
      const { data: node } = await AutomationWorkflowNodeService(
        this.$client
      ).create(workflow.id, type, beforeId, previousNodeId, previousNodeOutput)

      // Remove temp node and add real one
      commit('DELETE_ITEM', { workflow, nodeId: tempNode.id })
      commit('ADD_ITEM', { workflow, node })

      // If we have a `beforeNode`, we need to update its `previous_node_id`
      // and `previous_node_output`. The former so that it points to our newly
      // created node, and the latter so that it has a blank output.
      // This all happens in the backend, but we need the store to reflect the
      // change immediately.
      if (beforeNode) {
        commit('UPDATE_ITEM', {
          workflow,
          node: beforeNode,
          values: { previous_node_id: node.id, previous_node_output: '' },
        })
      }

      setTimeout(() => {
        const populatedNode = getters.findById(workflow, node.id)
        dispatch('select', { workflow, node: populatedNode })
      })

      return node
    } catch (error) {
      // If API fails, remove the temporary node
      commit('DELETE_ITEM', { workflow, nodeId: tempNode.id })
      // And restore the previous `beforeNode` values.
      if (beforeNode) {
        commit('UPDATE_ITEM', {
          workflow,
          node: beforeNode,
          values: beforeOldValues,
        })
      }
      throw error
    }
  },
  forceUpdate({ commit, dispatch }, { workflow, node, values, override }) {
    commit('UPDATE_ITEM', {
      workflow,
      node,
      values,
      override,
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
            values: data,
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
  forceDelete({ commit, dispatch, getters }, { workflow, nodeId }) {
    const node = getters.findById(workflow, nodeId)
    if (!node) return

    const nextNodes = getters.getNextNodes(workflow, node)
    const nextNode = nextNodes.length > 0 ? nextNodes[0] : null

    if (getters.getSelected(workflow)?.id === nodeId) {
      dispatch('select', { workflow, node: null })
    }

    if (nextNode) {
      if (node.previous_node_id) {
        commit('UPDATE_ITEM', {
          workflow,
          node: nextNode,
          values: {
            previous_node_id: node.previous_node_id,
            previous_node_output: node.previous_node_output,
          },
        })
      }
      dispatch('select', { workflow, node: nextNode })
    }

    commit('DELETE_ITEM', { workflow, nodeId })
  },
  async delete({ commit, dispatch, getters }, { workflow, nodeId }) {
    const node = getters.findById(workflow, nodeId)
    // Note that when we fetch the next node, we don't pass in the output,
    // this is because the next node in that scenario *won't have* an output.
    const nextNodes = getters.getNextNodes(workflow, node)
    const nextNode = nextNodes.length > 0 ? nextNodes[0] : null
    const originalNode = { ...node }
    if (getters.getSelected(workflow)?.id === nodeId) {
      dispatch('select', { workflow, node: null })
    }
    // If we have a node after the one we're deleting, we need to update its
    // `previous_node_id` and `previous_node_output` to point to the node
    // we're deleting.
    if (nextNode) {
      commit('UPDATE_ITEM', {
        workflow,
        node: nextNode,
        values: {
          previous_node_id: node.previous_node_id,
          previous_node_output: node.previous_node_output,
        },
      })
      dispatch('select', { workflow, node: nextNode })
    }
    commit('DELETE_ITEM', { workflow, nodeId })
    try {
      await AutomationWorkflowNodeService(this.$client).delete(nodeId)
    } catch (error) {
      commit('ADD_ITEM', { workflow, node: originalNode })
      throw error
    }
  },
  async replace({ commit, dispatch, getters }, { workflow, nodeId, newType }) {
    const node = getters.findById(workflow, nodeId)
    const nextNodes = getters.getNextNodes(workflow, node)
    const nextNode = nextNodes.length > 0 ? nextNodes[0] : null

    const { data: newNode } = await AutomationWorkflowNodeService(
      this.$client
    ).replace(nodeId, {
      new_type: newType,
    })
    commit('DELETE_ITEM', { workflow, nodeId })
    commit('ADD_ITEM', { workflow, node: newNode })

    // If the node that we replaced had a node after it, we need to update
    // its `previous_node_id` to point to the new node ID.
    if (nextNode) {
      commit('UPDATE_ITEM', {
        workflow,
        node: nextNode,
        values: { previous_node_id: newNode.id },
      })
    }

    dispatch('select', { workflow, node: newNode })
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
  async simulateDispatch(
    { commit, dispatch },
    { workflow, nodeId, updateSampleData }
  ) {
    const result = await AutomationWorkflowNodeService(
      this.$client
    ).simulateDispatch(nodeId, updateSampleData)
    const updatedNode = result.data

    commit('UPDATE_ITEM', {
      workflow,
      node: updatedNode,
      values: {
        simulate_until_node: updatedNode.simulate_until_node,
        service: updatedNode.service,
      },
    })
  },
}

const getters = {
  getNodes: (state) => (workflow) => {
    return workflow.nodes
  },
  getNodesOrdered: (state) => (workflow) => {
    return workflow.orderedNodes
  },
  findById: (state) => (workflow, nodeId) => {
    if (!workflow || !workflow.nodes || !nodeId) return null
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
  getNextNodes:
    (state, getters) =>
    (workflow, targetNode, outputUid = null) => {
      const nodes = getters.getNodesOrdered(workflow)
      const nextNodes = nodes.filter(
        (node) => node.previous_node_id === targetNode?.id
      )
      if (outputUid !== null) {
        return nextNodes.filter(
          (node) => node.previous_node_output === outputUid
        )
      }
      return nextNodes
    },
  getPreviousNode: (state, getters) => (workflow, node) => {
    return getters.findById(workflow, node?.previous_node_id)
  },
  getPreviousNodes:
    (state, getters) =>
    (
      workflow,
      targetNode,
      { targetFirst = false, includeSelf = false } = {}
    ) => {
      const getPreviousForNode = (node) => {
        const previousNode = getters.getPreviousNode(workflow, node)
        if (previousNode) {
          return [...getPreviousForNode(previousNode), previousNode]
        } else {
          return []
        }
      }
      const previous = includeSelf
        ? [...getPreviousForNode(targetNode), targetNode]
        : getPreviousForNode(targetNode)
      return targetFirst ? previous.reverse() : previous
    },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
