import { uuid } from '@baserow/modules/core/utils/string'
import AutomationWorkflowNodeService from '@baserow/modules/automation/services/automationWorkflowNode'
import { NodeEditorSidePanelType } from '@baserow/modules/automation/editorSidePanelTypes'
import { clone } from '@baserow/modules/core/utils/object'

import NodeGraphHandler from '@baserow/modules/automation/utils/nodeGraphHandler'

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
    if (override) {
      workflow.nodeMap[nodeToUpdate.id] = populateNode(values)
    } else {
      Object.assign(workflow.nodeMap[nodeToUpdate.id], values)
    }
  },
  DELETE_ITEM(state, { workflow, nodeId }) {
    const nodeIdStr = nodeId.toString()
    workflow.nodes = workflow.nodes.filter(
      (item) => item.id.toString() !== nodeIdStr
    )
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

    // Add the new node into the workflow
    commit('ADD_ITEM', { workflow, node })
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
  async graphInsert(
    { commit, dispatch, getters },
    { workflow, node, referenceNode, position, output }
  ) {
    const graphHandler = new NodeGraphHandler(workflow)
    graphHandler.insert(node, referenceNode, position, output)

    await dispatch(
      'automationWorkflow/forceUpdate',
      {
        workflow,
        values: { graph: graphHandler.graph },
      },
      { root: true }
    )
  },
  async graphRemove({ commit, dispatch, getters }, { workflow, node }) {
    const graphHandler = new NodeGraphHandler(workflow)
    graphHandler.remove(node)

    await dispatch(
      'automationWorkflow/forceUpdate',
      {
        workflow,
        values: { graph: graphHandler.graph },
      },
      { root: true }
    )
  },
  async graphMove(
    { commit, dispatch, getters },
    { workflow, nodeToMove, referenceNode, position, output }
  ) {
    const graphHandler = new NodeGraphHandler(workflow)
    graphHandler.move(nodeToMove, referenceNode, position, output)

    await dispatch(
      'automationWorkflow/forceUpdate',
      {
        workflow,
        values: { graph: graphHandler.graph },
      },
      { root: true }
    )
  },
  async graphReplace(
    { commit, dispatch, getters },
    { workflow, nodeToReplace, newNode }
  ) {
    const graphHandler = new NodeGraphHandler(workflow)
    graphHandler.replace(nodeToReplace, newNode)

    await dispatch(
      'automationWorkflow/forceUpdate',
      {
        workflow,
        values: { graph: graphHandler.graph },
      },
      { root: true }
    )
  },
  async create(
    { commit, dispatch, getters },
    { workflow, type, referenceNode, position, output }
  ) {
    // Using the `previousNodeId` and `previousNodeOutput` to determine
    // what the `beforeId` should be. We will have `beforeId` if we're
    // creating a node after `previousNodeId`, and `previousNodeId` has
    // a node that follows it.
    const nodeType = this.$registry.get('node', type)

    // Apply optimistic create
    const tempNode = nodeType.getDefaultValues({
      id: uuid(),
      type,
      workflow: workflow.id,
    })

    commit('ADD_ITEM', { workflow, node: tempNode })

    const initialGraph = clone(workflow.graph)

    dispatch('graphInsert', {
      workflow,
      node: tempNode,
      referenceNode,
      position,
      output,
    })

    try {
      const { data: node } = await AutomationWorkflowNodeService(
        this.$client
      ).create(workflow.id, type, referenceNode, position, output)

      commit('ADD_ITEM', { workflow, node })

      await dispatch('graphReplace', {
        workflow,
        nodeToReplace: tempNode,
        newNode: node,
      })

      // Remove temp node and add real one
      commit('DELETE_ITEM', { workflow, nodeId: tempNode.id })

      setTimeout(() => {
        const populatedNode = getters.findById(workflow, node.id)
        dispatch('select', { workflow, node: populatedNode })
      })

      return node
    } catch (error) {
      // If API fails, remove the temporary node
      await dispatch(
        'automationWorkflow/forceUpdate',
        {
          workflow,
          values: { graph: initialGraph },
        },
        { root: true }
      )
      commit('DELETE_ITEM', { workflow, nodeId: tempNode.id })

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
    const excludeValues = ['id']

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
      if (nextNode) {
        dispatch('select', { workflow, node: nextNode })
      }
    }

    commit('DELETE_ITEM', { workflow, nodeId })
  },
  async delete({ commit, dispatch, getters }, { workflow, nodeId }) {
    const node = getters.findById(workflow, nodeId)
    const originalNode = clone(node)

    const initialGraph = clone(workflow.graph)
    await dispatch('graphRemove', {
      workflow,
      node,
    })

    commit('DELETE_ITEM', { workflow, nodeId })
    try {
      await AutomationWorkflowNodeService(this.$client).delete(nodeId)
    } catch (error) {
      // We restore the removed node
      commit('ADD_ITEM', { workflow, node: originalNode })
      await dispatch(
        'automationWorkflow/forceUpdate',
        {
          workflow,
          values: { graph: initialGraph },
        },
        { root: true }
      )
      throw error
    }
  },
  async replace(
    { commit, dispatch, getters, rootGetters },
    { workflow, nodeId, newType }
  ) {
    const nodeToReplace = getters.findById(workflow, nodeId)

    const { data: newNode } = await AutomationWorkflowNodeService(
      this.$client
    ).replace(nodeId, {
      new_type: newType,
    })

    commit('ADD_ITEM', { workflow, node: newNode })

    await dispatch('graphReplace', {
      workflow,
      nodeToReplace,
      newNode,
    })

    commit('DELETE_ITEM', { workflow, nodeId })

    await dispatch(
      'automationWorkflow/forceUpdate',
      {
        workflow,
        values: { simulate_until_node_id: null },
      },
      { root: true }
    )

    setTimeout(() => {
      dispatch('select', { workflow, node: newNode })
    })
  },
  async move({ commit, dispatch, getters }, { workflow, moveData }) {
    const { movedNodeId, referenceNodeId, position, output } = moveData
    const movedNode = getters.findById(workflow, movedNodeId)
    const referenceNode = getters.findById(workflow, referenceNodeId)

    const [previousReferenceNode, previousPosition, previousOutput] =
      new NodeGraphHandler(workflow).getNodePosition(movedNode)

    dispatch('graphMove', {
      workflow,
      nodeToMove: movedNode,
      referenceNode,
      position,
      output,
    })

    try {
      // Perform the backend update.
      await AutomationWorkflowNodeService(this.$client).move(movedNodeId, {
        reference_node_id: referenceNodeId,
        position,
        output,
      })
    } catch (error) {
      // We revert the operation
      dispatch('graphMove', {
        workflow,
        nodeToMove: movedNode,
        referenceNode: previousReferenceNode,
        position: previousPosition,
        output: previousOutput,
      })

      throw error
    }
  },
  async duplicate({ commit, dispatch, getters }, { workflow, nodeId }) {
    const nodeToDuplicate = getters.findById(workflow, nodeId)
    if (!nodeToDuplicate) {
      return
    }

    // Get the node type to properly initialize the node
    const nodeType = this.$registry.get('node', nodeToDuplicate.type)

    // Use getDefaultValues like in create, but override with duplicated node's data
    const tempNode = nodeType.getDefaultValues({
      ...nodeToDuplicate, // Copy all properties from the original
      id: uuid(), // But give it a new ID
      workflow: workflow.id,
    })

    commit('ADD_ITEM', { workflow, node: tempNode })

    const initialGraph = clone(workflow.graph)

    // Insert the duplicated node after the original node using 'south' position
    await dispatch('graphInsert', {
      workflow,
      node: tempNode,
      referenceNode: nodeToDuplicate,
      position: 'south',
      output: '', // Default output for creating after a node
    })

    try {
      const { data: node } = await AutomationWorkflowNodeService(
        this.$client
      ).duplicate(nodeId)

      commit('ADD_ITEM', { workflow, node })

      await dispatch('graphReplace', {
        workflow,
        nodeToReplace: tempNode,
        newNode: node,
      })

      // Remove temp node and add real one
      commit('DELETE_ITEM', { workflow, nodeId: tempNode.id })

      setTimeout(() => {
        const populatedNode = getters.findById(workflow, node.id)
        dispatch('select', { workflow, node: populatedNode })
      })

      return node
    } catch (error) {
      // If API fails, restore the initial graph
      await dispatch(
        'automationWorkflow/forceUpdate',
        {
          workflow,
          values: { graph: initialGraph },
        },
        { root: true }
      )
      commit('DELETE_ITEM', { workflow, nodeId: tempNode.id })
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
  /**
   * Returns the immediate children of the given targetNode. For now we support only
   * one child but may be later we can support more.
   */
  getChildren: (state, getters) => (workflow, targetNode) => {
    return new NodeGraphHandler(workflow).getChildren(targetNode)
  },
  getNextNodes:
    (state, getters) =>
    (workflow, targetNode, outputUid = null) => {
      return new NodeGraphHandler(workflow).getNextNodes(targetNode, outputUid)
    },
  getAncestors: (state, getters) => (workflow, targetNode) => {
    const positions = new NodeGraphHandler(workflow).getPreviousPositions(
      targetNode
    )

    const parentNodes = positions
      .filter(([, position]) => position === 'child')
      .map(([prevNode]) => prevNode)

    return parentNodes
  },
  getPreviousNodes:
    (state, getters) =>
    (
      workflow,
      targetNode,
      { targetFirst = false, includeSelf = false, predicate = () => true } = {}
    ) => {
      const positions = new NodeGraphHandler(workflow).getPreviousPositions(
        targetNode
      )

      const previousNodes = positions
        .filter((position) => predicate(...position))
        .map(([prevNode]) => prevNode)
        .filter((node) => node)

      const previous = includeSelf
        ? [...previousNodes, targetNode]
        : previousNodes
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
