import { uuid } from '@baserow/modules/core/utils/string'
import AutomationWorkflowNodeService from '@baserow/modules/automation/services/automationWorkflowNode'
import { NodeEditorSidePanelType } from '@baserow/modules/automation/editorSidePanelTypes'
import { clone } from '@baserow/modules/core/utils/object'

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

const replace = (array, itemToReplace, replacement) => {
  const foundIndex = array.findIndex((item) => item === itemToReplace)
  return [
    ...array.slice(0, foundIndex),
    ...(Array.isArray(replacement) ? replacement : [replacement]),
    ...array.slice(foundIndex + 1),
  ]
}

const updateCachedValues = (workflow) => {
  if (!workflow || !workflow.nodes) return

  console.log('node received during update', workflow.nodes)

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
    console.log('add item', node)
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
    console.log('delete item', nodeId)
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
    console.log('force create', workflow, node)
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
    { workflow, node, positionNode, position, output }
  ) {
    const newGraph = clone(workflow.graph)
    console.log('graph before insert', JSON.stringify(newGraph))
    if (!positionNode) {
      // We are creating the trigger
      newGraph['0'] = node.id
      newGraph[node.id] = {}
    } else {
      let newNodeNext
      switch (position) {
        case 'south':
          if (!newGraph[positionNode.id].next) {
            newGraph[positionNode.id].next = {}
          }
          if (!newGraph[positionNode.id].next[output]) {
            newGraph[positionNode.id].next[output] = []
          }

          newNodeNext = newGraph[positionNode.id].next[output]
          newGraph[positionNode.id].next[output] = [node.id]

          break
        case 'child':
          if (!newGraph[positionNode.id].child) {
            newGraph[positionNode.id].child = []
          }
          newNodeNext = newGraph[positionNode.id].child
          newGraph[positionNode.id].child = [node.id]

          break
        default:
          throw new Error('Unexpected position')
      }
      newGraph[node.id] = {
        next: { '': newNodeNext },
      }
    }

    console.log('graph after insert', JSON.stringify(newGraph))

    await dispatch(
      'automationWorkflow/forceUpdate',
      {
        workflow,
        values: { graph: newGraph },
      },
      { root: true }
    )
  },
  async graphRemove({ commit, dispatch, getters }, { workflow, node }) {
    const newGraph = clone(workflow.graph)

    const [previousPositionNode, position, output] = getters.getNodePosition(
      workflow,
      node
    )

    console.log('previous', previousPositionNode, position, output)

    const nodeInfo = newGraph[node.id]
    const previousPositionNodeInfo = newGraph[previousPositionNode.id]

    console.log('graph before removal', JSON.stringify(newGraph))
    console.log('previous node info', previousPositionNodeInfo)

    switch (position) {
      case 'south':
        // We move next nodes of removed node to the previous node
        previousPositionNodeInfo.next[output] = replace(
          previousPositionNodeInfo.next[output],
          node.id,
          Object.values(nodeInfo.next || {}).flat()
        )

        console.log(replace([1], 1, 2))
        console.log(previousPositionNodeInfo.next[output])
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

    delete newGraph[node.id]

    console.log('new graph after removal', JSON.stringify(newGraph))

    await dispatch(
      'automationWorkflow/forceUpdate',
      {
        workflow,
        values: { graph: newGraph },
      },
      { root: true }
    )
  },
  async graphMove(
    { commit, dispatch, getters },
    { workflow, nodeToMove, positionNode, position, output }
  ) {
    const previousChild = workflow.graph[nodeToMove.id].child
    await dispatch('graphRemove', {
      workflow,
      node: nodeToMove,
    })

    await dispatch('graphInsert', {
      workflow,
      node: nodeToMove,
      positionNode,
      position,
      output,
    })
    const newGraph = clone(workflow.graph)
    newGraph[nodeToMove.id].child = previousChild

    await dispatch(
      'automationWorkflow/forceUpdate',
      {
        workflow,
        values: { graph: newGraph },
      },
      { root: true }
    )
  },
  async graphReplace(
    { commit, dispatch, getters },
    { workflow, nodeToReplace, newNode }
  ) {
    const [positionNode, position, output] = getters.getNodePosition(
      workflow,
      nodeToReplace
    )
    await dispatch('graphRemove', {
      workflow,
      node: nodeToReplace,
    })
    await dispatch('graphInsert', {
      workflow,
      node: newNode,
      positionNode,
      position,
      output,
    })
  },
  async create(
    { commit, dispatch, getters },
    { workflow, type, positionNode, position, output }
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
      positionNode,
      position,
      output,
    })

    try {
      const { data: node } = await AutomationWorkflowNodeService(
        this.$client
      ).create(workflow.id, type, positionNode, position, output)

      // Remove temp node and add real one
      commit('DELETE_ITEM', { workflow, nodeId: tempNode.id })
      commit('ADD_ITEM', { workflow, node })

      // We remove the temp node
      await dispatch(
        'automationWorkflow/forceUpdate',
        {
          workflow,
          values: { graph: initialGraph },
        },
        { root: true }
      )
      // And add the received one
      dispatch('graphInsert', {
        workflow,
        node,
        positionNode,
        position,
        output,
      })

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
    dispatch('graphRemove', {
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
  async replace({ commit, dispatch, getters }, { workflow, nodeId, newType }) {
    const nodeToReplace = getters.findById(workflow, nodeId)

    const { data: newNode } = await AutomationWorkflowNodeService(
      this.$client
    ).replace(nodeId, {
      new_type: newType,
    })

    commit('ADD_ITEM', { workflow, node: newNode })

    dispatch('graphReplace', {
      workflow,
      nodeToReplace,
      newNode,
    })

    commit('DELETE_ITEM', { workflow, nodeId })

    setTimeout(() => {
      dispatch('select', { workflow, node: newNode })
    })
  },
  async move({ commit, dispatch, getters }, { workflow, moveData }) {
    const { movedNodeId, positionNodeId, position, output } = moveData
    const movedNode = getters.findById(workflow, movedNodeId)
    const positionNode = getters.findById(workflow, positionNodeId)

    const [previousPositionNode, previousPosition, previousOutput] =
      getters.getNodePosition(workflow, movedNode)

    dispatch('graphMove', {
      workflow,
      nodeToMove: movedNode,
      positionNode,
      position,
      output,
    })

    try {
      // Perform the backend update.
      await AutomationWorkflowNodeService(this.$client).move(movedNodeId, {
        position_node_id: positionNodeId,
        position,
        output,
      })
    } catch (error) {
      // We revert the operation
      dispatch('graphMove', {
        workflow,
        nodeToMove: movedNode,
        positionNode: previousPositionNode,
        position: previousPosition,
        output: previousOutput,
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
  findById: (state) => (workflow, nodeId) => {
    if (!workflow || !workflow.nodes || !nodeId) return null
    const nodeIdStr = nodeId.toString()
    if (workflow.nodeMap && workflow.nodeMap[nodeIdStr]) {
      return workflow.nodeMap[nodeIdStr]
    }
    return null
  },
  getNodePosition: (state, getters) => (workflow, node) => {
    if (workflow.graph['0'] === node.id) {
      return [null, 'south', '']
    }
    for (const [nodeId, value] of Object.entries(workflow.graph)) {
      if (value.next) {
        const outputFound = Object.entries(value.next).find(([, nextOnEdge]) =>
          nextOnEdge.includes(node.id)
        )
        if (outputFound) {
          const previousNode = getters.findById(workflow, nodeId)
          return [previousNode, 'south', outputFound[0]]
        }
      }
      if (value.child) {
        if (value.child.includes(node.id)) {
          const parentNode = getters.findById(workflow, nodeId)
          return [parentNode, 'child', '']
        }
      }
    }
    throw new Error('Node not found in graph')
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
    return (workflow.graph[targetNode.id]?.child || [])
      .map((id) => getters.findById(workflow, id))
      .filter((node) => node)
  },
  getNextNodes:
    (state, getters) =>
    (workflow, targetNode, outputUid = '') => {
      if (workflow.graph[targetNode.id]?.next) {
        return (workflow.graph[targetNode.id].next[outputUid] || [])
          .map((id) => getters.findById(workflow, id))
          .filter((node) => node)
      }
      return []
    },
  getPreviousNode: (state, getters) => (workflow, node) => {
    const found = Object.entries(workflow.graph).find(([nodeId, value]) => {
      if (value.next) {
        try {
          const outputFound = Object.values(value.next).find((nextOnEdge) =>
            nextOnEdge.includes(node.id)
          )
          if (outputFound) {
            return true
          }
        } catch (e) {
          return false
        }
      }
      return false
    })
    if (found) {
      return getters.findById(workflow, found[0])
    }
    return null
  },
  getPreviousNodes:
    (state, getters) =>
    (
      workflow,
      targetNode,
      { targetFirst = false, includeSelf = false } = {}
    ) => {
      // TODO
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
