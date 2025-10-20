import { uuid } from '@baserow/modules/core/utils/string'
import AutomationWorkflowNodeService from '@baserow/modules/automation/services/automationWorkflowNode'
import { NodeEditorSidePanelType } from '@baserow/modules/automation/editorSidePanelTypes'

const state = {
  selectedNodeId: null,
  draggingNodeId: null,
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
  SET_DRAGGING_NODE_ID(state, nodeId) {
    state.draggingNodeId = nodeId
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
    {
      workflow,
      type,
      previousNodeId = null,
      previousNodeOutput = '',
      parentNodeId = null,
    }
  ) {
    // Using the `previousNodeId` and `previousNodeOutput` to determine
    // what the `beforeId` should be. We will have `beforeId` if we're
    // creating a node after `previousNodeId`, and `previousNodeId` has
    // a node that follows it.
    const nodeType = this.$registry.get('node', type)

    let beforeNode = null

    if (previousNodeId) {
      const previousNode = getters.findById(workflow, previousNodeId)
      const nextNodes = getters.getNextNodes(
        workflow,
        previousNode,
        previousNodeOutput
      )

      beforeNode = nextNodes.length > 0 ? nextNodes[0] : null
    } else {
      const parentNode = getters.findById(workflow, parentNodeId)
      const children = getters.getChildren(workflow, parentNode)

      beforeNode = children.length > 0 ? children[0] : null
    }

    const beforeId = beforeNode?.id || null
    const beforeOldValues = beforeNode
      ? {
          previous_node_id: beforeNode.previous_node_id,
          previous_node_output: beforeNode.previous_node_output,
          parent_node_id: beforeNode.parent_node_id,
        }
      : {}

    // Apply optimistic create
    const tempNode = nodeType.getDefaultValues({
      id: uuid(),
      type,
      previous_node_id: previousNodeId,
      previous_node_output: previousNodeOutput,
      parent_node_id: parentNodeId,
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
      ).create(
        workflow.id,
        type,
        beforeId,
        previousNodeId,
        previousNodeOutput,
        parentNodeId
      )

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
    const { data: newNode } = await AutomationWorkflowNodeService(
      this.$client
    ).replace(nodeId, {
      new_type: newType,
    })
    // Update nodes that follow `nodeId` so that their
    // `previous_node_id` point to the newly created node.
    dispatch('updateNextNodesValues', {
      workflow,
      nodeId,
      valuesToUpdate: { previous_node_id: newNode.id },
    })
    commit('DELETE_ITEM', { workflow, nodeId })
    commit('ADD_ITEM', { workflow, node: newNode })

    setTimeout(() => {
      dispatch('select', { workflow, node: newNode })
    })
  },
  async move({ commit, dispatch, getters }, { workflow, moveData }) {
    const { movedNodeId, afterNodeId, afterNodeOutput, parentNodeId } = moveData

    const movedNode = getters.findById(workflow, movedNodeId)
    const originSnapshot = { ...movedNode }
    const originNextNodesSnapshot = getters
      .getNextNodes(workflow, movedNode)
      .map((n) => ({
        id: n.id,
        previous_node_id: n.previous_node_id,
        previous_node_output: n.previous_node_output,
      }))

    // We move the node after this node if any
    const afterNode = afterNodeId
      ? getters.findById(workflow, afterNodeId)
      : null

    // We move the node as a child of this node if any
    const parentNode = parentNodeId
      ? getters.findById(workflow, parentNodeId)
      : null

    let afterNextNodesSnapshot
    if (afterNode === null) {
      // We are moving the node as first child of a container
      // So the immediate children of this node are the 'next nodes'
      afterNextNodesSnapshot = getters
        .getChildren(workflow, parentNode)
        .map((n) => ({
          id: n.id,
          previous_node_id: n.previous_node_id,
          previous_node_output: n.previous_node_output,
        }))
    } else {
      afterNextNodesSnapshot = getters
        .getNextNodes(workflow, afterNode)
        .map((n) => ({
          id: n.id,
          previous_node_id: n.previous_node_id,
          previous_node_output: n.previous_node_output,
        }))
    }

    try {
      // We start by moving the dragged node's next nodes, pre-move, so that
      // they all go "up" a level, they will point to the dragged node's previous
      // node id and output.
      dispatch('updateNextNodesValues', {
        workflow,
        nodeId: movedNode.id,
        valuesToUpdate: {
          previous_node_id: movedNode.previous_node_id,
          previous_node_output: movedNode.previous_node_output,
        },
      })

      // Next, we deal with the target node's next nodes, they need to point to
      // the dragged node. We'll only update the `previous_node_output` to a
      // blank string if we're moving the node to a specific output.
      dispatch('updateNextNodesValues', {
        workflow,
        nodeId: afterNode ? afterNode.id : null,
        parentNodeId: parentNode ? parentNode.id : null,
        valuesToUpdate: {
          previous_node_id: movedNode.id,
          ...(afterNodeOutput ? { previous_node_output: '' } : {}),
        },
        outputUid: afterNodeOutput,
      })

      // Finally, we update the dragged node itself, to point to the target
      // node and output.
      commit('UPDATE_ITEM', {
        workflow,
        node: movedNode,
        values: {
          previous_node_id: afterNodeId,
          previous_node_output: afterNodeOutput,
          parent_node_id: parentNodeId,
        },
      })

      // Perform the backend update.
      await AutomationWorkflowNodeService(this.$client).move(movedNodeId, {
        previous_node_id: afterNodeId,
        previous_node_output: afterNodeOutput,
        parent_node_id: parentNodeId,
      })
    } catch (error) {
      // Something went wrong, revert our changes.
      originNextNodesSnapshot.forEach((snap) => {
        const snapNode = getters.findById(workflow, snap.id)
        commit('UPDATE_ITEM', {
          workflow,
          node: snapNode,
          values: {
            previous_node_id: snap.previous_node_id,
            previous_node_output: snap.previous_node_output,
          },
        })
      })
      afterNextNodesSnapshot.forEach((snap) => {
        const snapNode = getters.findById(workflow, snap.id)
        commit('UPDATE_ITEM', {
          workflow,
          node: snapNode,
          values: {
            previous_node_id: snap.previous_node_id,
            previous_node_output: snap.previous_node_output,
          },
        })
      })
      // Move `movedNode` back to its original position.
      commit('UPDATE_ITEM', {
        workflow,
        node: movedNode,
        values: originSnapshot,
      })

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
  setDraggingNodeId({ commit }, nodeId) {
    commit('SET_DRAGGING_NODE_ID', nodeId)
  },
  async simulateDispatch({ commit, dispatch }, { nodeId }) {
    await AutomationWorkflowNodeService(this.$client).simulateDispatch(nodeId)
  },
  /**
   * Updates all the next nodes of a given node with the provided values.
   * This used when a node is replaced, or moved, as the next nodes need to
   * be updated to reflect the new previous node id and output.
   */
  _updateNextNodesValues(
    { commit, getters },
    { workflow, nodeId, valuesToUpdate, outputUid = null, parentNodeId = null }
  ) {
    const node = getters.findById(workflow, nodeId)
    const nextNodes = getters.getNextNodes(workflow, node, outputUid)
    nextNodes.forEach((nextNode) => {
      commit('UPDATE_ITEM', {
        workflow,
        node: nextNode,
        values: valuesToUpdate,
      })
    })
  },
  /**
   * Updates all the next nodes of a given node with the provided values.
   * This used when a node is replaced, or moved, as the next nodes need to
   * be updated to reflect the new previous node id and output.
   */
  updateNextNodesValues(
    { commit, getters },
    {
      workflow,
      nodeId = null,
      parentNodeId = null,
      valuesToUpdate,
      outputUid = null,
    }
  ) {
    let nextNodes
    if (nodeId) {
      const node = getters.findById(workflow, nodeId)
      nextNodes = getters.getNextNodes(workflow, node, outputUid)
    } else {
      const parentNode = getters.findById(workflow, parentNodeId)
      nextNodes = getters.getChildren(workflow, parentNode)
    }
    nextNodes.forEach((nextNode) => {
      commit('UPDATE_ITEM', {
        workflow,
        node: nextNode,
        values: valuesToUpdate,
      })
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
  getDraggingNodeId(state) {
    return state.draggingNodeId
  },
  getParent: (state, getters) => (workflow, targetNode) => {
    if (targetNode.parent_node_id) {
      return getters.findById(workflow, targetNode.parent_node_id)
    }
    return null
  },
  getAncestors: (state, getters) => (workflow, targetNode) => {
    const parent = getters.getParent(workflow, targetNode)
    if (parent) {
      return [...getters.getAncestors(workflow, parent), parent]
    }
    return []
  },
  /**
   * Returns the immediate children of the given targetNode. For now we support only
   * one child but may be later we can support more.
   */
  getChildren: (state, getters) => (workflow, targetNode) => {
    const nodes = getters.getNodesOrdered(workflow)
    return nodes.filter(
      (node) =>
        node.parent_node_id === targetNode.id && node.previous_node_id === null
    )
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
        }
        const parent = getters.getParent(workflow, node)

        if (parent) {
          return [...getPreviousForNode(parent), parent]
        }

        return []
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
