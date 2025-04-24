import { computed } from 'vue'
import { getNodesInside, isEdgeVisible } from '../utils'
import { defaultEdgeTypes, defaultNodeTypes } from '../utils/defaultNodesEdges'

export function useGetters(state, nodeLookup, edgeLookup) {
  /**
   * @deprecated will be removed in next major version; use findNode instead
   */
  const getNode = computed(() => (id) => nodeLookup.value.get(id))

  /**
   * @deprecated will be removed in next major version; use findEdge instead
   */
  const getEdge = computed(() => (id) => edgeLookup.value.get(id))

  const getEdgeTypes = computed(() => {
    const edgeTypes = {
      ...defaultEdgeTypes,
      ...state.edgeTypes,
    }

    const keys = Object.keys(edgeTypes)

    for (const e of state.edges) {
      e.type && !keys.includes(e.type) && (edgeTypes[e.type] = e.type)
    }

    return edgeTypes
  })

  const getNodeTypes = computed(() => {
    const nodeTypes = {
      ...defaultNodeTypes,
      ...state.nodeTypes,
    }

    const keys = Object.keys(nodeTypes)

    for (const n of state.nodes) {
      n.type && !keys.includes(n.type) && (nodeTypes[n.type] = n.type)
    }

    return nodeTypes
  })

  const getNodes = computed(() => {
    if (state.onlyRenderVisibleElements) {
      return getNodesInside(
        state.nodes,
        {
          x: 0,
          y: 0,
          width: state.dimensions.width,
          height: state.dimensions.height,
        },
        state.viewport,
        true
      )
    }

    return state.nodes
  })

  const getEdges = computed(() => {
    if (state.onlyRenderVisibleElements) {
      const visibleEdges = []

      for (const edge of state.edges) {
        const source = nodeLookup.value.get(edge.source)
        const target = nodeLookup.value.get(edge.target)

        if (
          isEdgeVisible({
            sourcePos: source.computedPosition || { x: 0, y: 0 },
            targetPos: target.computedPosition || { x: 0, y: 0 },
            sourceWidth: source.dimensions.width,
            sourceHeight: source.dimensions.height,
            targetWidth: target.dimensions.width,
            targetHeight: target.dimensions.height,
            width: state.dimensions.width,
            height: state.dimensions.height,
            viewport: state.viewport,
          })
        ) {
          visibleEdges.push(edge)
        }
      }

      return visibleEdges
    }

    return state.edges
  })

  const getElements = computed(() => [...getNodes.value, ...getEdges.value])

  const getSelectedNodes = computed(() => {
    const selectedNodes = []
    for (const node of state.nodes) {
      if (node.selected) {
        selectedNodes.push(node)
      }
    }

    return selectedNodes
  })

  const getSelectedEdges = computed(() => {
    const selectedEdges = []
    for (const edge of state.edges) {
      if (edge.selected) {
        selectedEdges.push(edge)
      }
    }

    return selectedEdges
  })

  const getSelectedElements = computed(() => [
    ...getSelectedNodes.value,
    ...getSelectedEdges.value,
  ])

  /**
   * @deprecated will be removed in next major version; use `useNodesInitialized` instead
   */
  const getNodesInitialized = computed(() => {
    const initializedNodes = []

    for (const node of state.nodes) {
      if (
        !!node.dimensions.width &&
        !!node.dimensions.height &&
        node.handleBounds !== undefined
      ) {
        initializedNodes.push(node)
      }
    }

    return initializedNodes
  })

  /**
   * @deprecated will be removed in next major version; use `useNodesInitialized` instead
   */
  const areNodesInitialized = computed(
    () =>
      getNodes.value.length > 0 &&
      getNodesInitialized.value.length === getNodes.value.length
  )

  return {
    getNode,
    getEdge,
    getElements,
    getEdgeTypes,
    getNodeTypes,
    getEdges,
    getNodes,
    getSelectedElements,
    getSelectedNodes,
    getSelectedEdges,
    getNodesInitialized,
    areNodesInitialized,
  }
}
