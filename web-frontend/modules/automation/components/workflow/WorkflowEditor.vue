<template>
  <VueFlow
    class="workflow-editor"
    :nodes="displayNodes"
    :edges="computedEdges"
    :zoom-on-scroll="false"
    :nodes-draggable="nodesDraggable"
    :zoom-on-drag="zoomOnScroll"
    :pan-on-scroll="panOnScroll"
    :node-drag-threshold="2000"
    :zoom-on-double-click="zoomOnDoubleClick"
    fit-view-on-init
    :max-zoom="1"
    :min-zoom="0.5"
  >
    <Controls :show-interactive="false" />
    <Background pattern-color="#ededed" :size="3" :gap="15" />

    <template #node-workflow-node="slotProps">
      <WorkflowNode
        :id="slotProps.id"
        :label="slotProps.label"
        :selected="slotProps.selected"
        :dragging="slotProps.dragging"
        :position="slotProps.position"
        :data="slotProps.data"
        @remove-node="handleRemoveNode"
        @replace-node="handleReplaceNode"
      />
    </template>

    <template #node-workflow-add-button-node="slotProps">
      <WorkflowAddBtnNode
        :id="slotProps.id"
        :ref="`addWorkflowBtnNode-${slotProps.id}`"
        :data="slotProps.data"
        :label="slotProps.label"
        :selected="slotProps.selected"
        :dragging="slotProps.dragging"
        :position="slotProps.position"
        @addNode="toggleCreateContext(slotProps.id)"
      />
      <WorkflowNodeContext
        :ref="`nodeContext-${slotProps.id}`"
        @change="
          createNode($event, slotProps.data.nodeId, slotProps.data.outputUid)
        "
      ></WorkflowNodeContext>
    </template>

    <template #edge-workflow-edge="slotProps">
      <WorkflowEdge
        :id="slotProps.id"
        :source-x="slotProps.sourceX"
        :source-y="slotProps.sourceY"
        :target-x="slotProps.targetX"
        :target-y="slotProps.targetY"
      />
    </template>
  </VueFlow>
</template>

<script setup>
import { VueFlow, useVueFlow } from '@vue2-flow/core'
import { Background } from '@vue2-flow/background'
import { Controls } from '@vue2-flow/controls'
import { ref, computed, watch, toRefs, onMounted } from 'vue'
import {
  inject,
  useContext,
  nextTick,
  getCurrentInstance,
  useStore,
} from '@nuxtjs/composition-api'
import _ from 'lodash'
import WorkflowNode from '@baserow/modules/automation/components/workflow/WorkflowNode'
import WorkflowAddBtnNode from '@baserow/modules/automation/components/workflow/WorkflowAddBtnNode'
import WorkflowEdge from '@baserow/modules/automation/components/workflow/WorkflowEdge'
import WorkflowNodeContext from '@baserow/modules/automation/components/workflow/WorkflowNodeContext'

const props = defineProps({
  nodes: {
    type: Array,
    required: true,
  },
  value: {
    type: [String, Number],
    default: null,
  },
  isAddingNode: {
    type: Boolean,
    default: false,
  },
})

const instance = getCurrentInstance()
const refs = instance.proxy.$refs

const emit = defineEmits(['add-node', 'remove-node', 'input'])

const { addSelectedNodes, onMove, onNodeClick, onPaneClick } = useVueFlow()

const { value: selectedNodeId } = toRefs(props)

const { app } = useContext()

const nodesDraggable = ref(true)
const zoomOnScroll = ref(false)
const panOnScroll = ref(true)
const zoomOnDoubleClick = ref(false)

const workflowDebug = inject('workflowDebug')
const workflowReadOnly = inject('workflowReadOnly')

// Constants for dimensions and positioning
const DATA_NODE_HEIGHT = 72 // How tall is a node?
const DATA_NODE_WIDTH = 412 // How wide is a node?
const DATA_NODE_MIDDLE = DATA_NODE_WIDTH / 2 // The middle of a node.

const NODE_PADDING = 30 // Padding between node edges

const ADD_BUTTON_WIDTH = 32 // The width of the add button
const ADD_BUTTON_MIDDLE = ADD_BUTTON_WIDTH / 2 // The middle of the add button

const EDGE_HEIGHT = 100 // The height an edge occupies
const EDGE_WITHOUT_OUTPUT_NODE_WIDTH = 100 // The width of an edge when there is no output node
const EDGE_WITHOUT_OUTPUT_NODE_INPUT = EDGE_WITHOUT_OUTPUT_NODE_WIDTH / 2 // The height of an edge when there is no output node

watch(
  selectedNodeId,
  (newId) => {
    if (newId) addSelectedNodes([{ id: newId.toString() }])
  },
  { immediate: true }
)

/**
 * Recursively calculates the dimensions of a node and its edges. An object is
 * returned where each key is a node ID and the value is an object containing
 * the dimensions of that node, including its width, height, input position,
 * (left) output position, and the dimensions of its edges.
 * @param node - The node for which to calculate dimensions.
 * @returns {object} - An object containing the dimensions of the node and its edges.
 */
const calculateNodeDimensions = (node) => {
  // We start by getting this node's type, and then fetching the one or more
  // nodes which follow `node` in the workflow, we'll use them to recursively
  // compute their dimensions.
  const nodeType = app.$registry.get('node', node.type)
  const nextNodes = store.getters['automationWorkflowNode/getNextNodes'](
    workflow.value,
    node
  )

  // Map over each next node, and calculate their dimensions.
  const nextNodeDimensions = Object.assign(
    {},
    ...nextNodes.map((nextNode) => calculateNodeDimensions(nextNode))
  )

  // We now have an object containing all the next node dimensions, but we
  // don't yet have the dimensions of the edge. We do that now by finding
  // the edges associated with this node.
  const nodeEdges = nodeType.getEdges({ node })
  const edgeDimensions = Object.assign(
    {},
    ...nodeEdges.map((edge) => {
      // Get all the next nodes after `node` which are connected to this edge.
      const nextNodesOnEdge = store.getters[
        'automationWorkflowNode/getNextNodes'
      ](workflow.value, node, edge.uid)

      // If we have found one or more output nodes associated with this edge...
      if (nextNodesOnEdge.length) {
        // The width will be the sum of the next nodes' dimensions, with
        // some padding added between them.
        const width = _.sum(
          nextNodesOnEdge.map(
            (nextNode) =>
              nextNodeDimensions[nextNode.id].width +
              (nextNodesOnEdge.length - 1) * NODE_PADDING
          )
        )

        // We compute the position of the input by taking the
        // middle between the first and the last input
        const leftMost = nextNodeDimensions[nextNodesOnEdge[0].id]
        const rightMost = nextNodeDimensions[nextNodesOnEdge.at(-1).id]
        const edgeWidth =
          width - leftMost.input - (rightMost.width - rightMost.input)

        return {
          [edge.uid]: {
            width,
            input: leftMost.input + edgeWidth / 2,
          },
        }
      }
      // We did not find any output nodes associated with this edge, so
      // to size this bounding box correctly, we'll use a default width
      // and input value.
      return {
        [edge.uid]: {
          width: EDGE_WITHOUT_OUTPUT_NODE_WIDTH,
          input: EDGE_WITHOUT_OUTPUT_NODE_INPUT,
        },
      }
    })
  )

  // Calculate the sum of all widths of the edges, including padding,
  // to determine the total width of the node. We will use the MAX
  // of `widthSum` and `DATA_NODE_WIDTH` to ensure that the node
  // is *at least* as wide as the default data node width.
  const widthSum =
    _.sum(nodeEdges.map((edge) => edgeDimensions[edge.uid].width)) +
    (nodeEdges.length - 1) * NODE_PADDING
  const width = Math.max(widthSum, DATA_NODE_WIDTH)

  // We take the left and right edge to compute the input position for this node
  const leftMost = edgeDimensions[nodeEdges[0].uid]
  const rightMost = edgeDimensions[nodeEdges.at(-1).uid]
  const edgesWidth =
    width - leftMost.input - (rightMost.width - rightMost.input)
  const input = leftMost.input + edgesWidth / 2

  // The height of the node is determined by the edge height, and
  // the default height of the data node itself.
  const height = EDGE_HEIGHT + DATA_NODE_HEIGHT

  return {
    ...nextNodeDimensions,
    ...{
      [node.id]: {
        width,
        // Sometimes the width of edges is smaller than the width of node
        outputLeft: input - (width - widthSum) / 2,
        height,
        input,
        edges: edgeDimensions,
      },
    },
  }
}

/**
 * Recursively calculates the positions of nodes and their edges in the workflow.
 * It returns an object where each key is a node ID and the value is an object
 * containing the position of the node, the positions of the add buttons for each
 * edge, and the edges themselves.
 *
 * @param dimensions - An object containing the dimensions of each node,
 *  as returned by `calculateNodeDimensions`.
 * @param node - The current node for which to calculate positions.
 * @param x - The x-coordinate for the current node's position.
 * @param y - The y-coordinate for the current node's position.
 * @returns {object} - An object containing the positions of nodes, add buttons, and edges.
 */
const calculatePositions = (dimensions, node, { x = 0, y = 0 } = {}) => {
  // We start by getting the type of the node, which will be used
  // to fetch the edges associated with this node.
  const nodeType = app.$registry.get('node', node.type)

  // Store two different values: the X-coordinate of the current edge,
  // which is the position of the output, plus the middle of the node,
  // and the current X-coordinate, which is the position of the output.
  let currentEdgeX = x - dimensions[node.id].outputLeft + DATA_NODE_MIDDLE
  let currentX = x - dimensions[node.id].outputLeft // As input is the number of pixel from the left

  // Find the edges associated with this node, very frequently it'll be one.
  const nodeEdges = nodeType.getEdges({ node })
  const oneEdge = nodeEdges.length === 1

  // Keep track of `vue-flow` edges and add button positions.
  const edges = []
  const addButtonPositions = []

  // Build an object containing the positions of `node`'s next nodes and their edges.
  const nextNodePositions = Object.assign(
    {},
    ...nodeEdges.map((edge, edgeIndex) => {
      // Are there any output nodes associated with this edge?
      const nextNodesAlongEdge = store.getters[
        'automationWorkflowNode/getNextNodes'
      ](workflow.value, node, edge.uid)

      // Generate a unique key for the add button based on the node ID and edge UID.
      const buttonKey = `edge-${node.id}-${edge.uid || 'default'}`

      // Add an edge between `node` and its add button
      edges.push({
        id: `e-${workflowDebug.value}-${node.id}-${buttonKey}-${edge.uid}`,
        source: node.id.toString(),
        target: buttonKey,
        data: { outputUid: edge.uid },
        label: workflowDebug.value
          ? `from:${node.id} to:addBtn${edgeIndex}`
          : edge.label,
        type: oneEdge ? 'straight' : 'smoothstep',
      })

      // We define the position of the buttons
      addButtonPositions.push({
        uid: edge.uid,
        key: buttonKey,
        x:
          currentEdgeX -
          ADD_BUTTON_MIDDLE +
          dimensions[node.id].edges[edge.uid].input,
        y: y + (oneEdge ? 90 : 130),
      })

      const noNodeOnEdge = nextNodesAlongEdge.length === 0
      const edgeWidth = dimensions[node.id].edges[edge.uid].width

      if (noNodeOnEdge) {
        // The currentX didn't change as we have no node, but it has to increase
        currentX += edgeWidth + NODE_PADDING
      }
      currentEdgeX += edgeWidth + NODE_PADDING

      return Object.assign(
        {},
        ...nextNodesAlongEdge.map((nextNode) => {
          // Add edge between the add button and next node
          edges.push({
            id: `e-${workflowDebug.value}-${nextNode.id}-${buttonKey}-${edge.uid}`,
            source: buttonKey,
            target: nextNode.id.toString(),
            data: { outputUid: edge.uid },
            label: workflowDebug.value
              ? `from:${nextNode.id} to:addBtn${edgeIndex}`
              : '',
            type: nextNodesAlongEdge.length === 1 ? 'straight' : 'smoothstep',
          })

          // The next X is the input position of the next node
          const nextX = currentX + dimensions[nextNode.id].input
          const nextY = y + dimensions[node.id].height
          currentX += dimensions[nextNode.id].width + NODE_PADDING // Moving to next node

          return calculatePositions(dimensions, nextNode, {
            x: nextX,
            y: nextY,
          })
        })
      )
    })
  )

  return {
    ...nextNodePositions,
    [node.id]: {
      x,
      y,
      addButtonPositions,
      edges,
    },
  }
}

/**
 * When the component is mounted, we emit the first node's ID. This is
 * to ensure that the first node (the trigger) is selected by default.
 */
onMounted(() => {
  emit('input', props.nodes[0].id)
})

const automation = inject('automation')

const positions = computed(() => {
  const trigger = props.nodes.find((node) => node.previous_node_id === null)
  const dimensions = calculateNodeDimensions(trigger)
  return calculatePositions(dimensions, trigger)
})

const displayNodes = computed(() => {
  return props.nodes
    .map((dataNode) => {
      const nodeType = app.$registry.get('node', dataNode.type)
      const nodeNode = {
        type: 'workflow-node',
        label: nodeType.getLabel({
          automation: automation.value,
          node: dataNode,
        }),
        id: dataNode.id.toString(),
        position: positions.value[dataNode.id],
        data: {
          nodeId: dataNode.id,
          isTrigger: nodeType.isTrigger,
          readOnly: workflowReadOnly.value,
          debug: workflowDebug.value,
          outputUid: dataNode.previous_node_output,
        },
      }

      const addButtonsNodes = positions.value[
        dataNode.id
      ].addButtonPositions.map((addButtonPosition) => ({
        id: addButtonPosition.key,
        type: 'workflow-add-button-node',
        position: addButtonPosition,
        data: {
          nodeId: dataNode.id,
          outputUid: addButtonPosition.uid,
          debug: workflowDebug.value,
          disabled: props.isAddingNode || workflowReadOnly.value,
        },
      }))

      return [nodeNode, ...addButtonsNodes]
    })
    .flat()
})

const store = useStore()
const workflow = inject('workflow')

const computedEdges = computed(() => {
  return Object.values(positions.value)
    .map((nodePosition) => nodePosition.edges)
    .flat()
})

/**
 * When the pane is clicked, we emit `null` which
 * clears the selected node in the node store.
 */
onPaneClick(() => {
  emit('input', null)
})

/**
 * When a 'workflow-node' node is clicked, we emit the node's
 * ID to set it as the selected node in the node store.
 */
onNodeClick(({ node }) => {
  if (node.type === 'workflow-node') {
    emit('input', node.id)
  }
})

/**
 * When the pane is moved, if we have an active node context,
 * we hide it. This is to ensure that the context menu does not stay
 * open when the user interacts with the workflow.
 */
const activeNodeContext = ref(null)
onMove(() => {
  activeNodeContext.value?.hide()
})

const toggleCreateContext = async (nodeId) => {
  await nextTick()
  const nodeContext = refs[`nodeContext-${nodeId}`]
  activeNodeContext.value = nodeContext
  const nodeAddBtn = refs[`addWorkflowBtnNode-${nodeId}`]
  nodeContext.show(nodeAddBtn.$el, 'bottom', 'left', 10, -225)
}

const createNode = (nodeType, previousNodeId, previousNodeOutput) => {
  emit('add-node', {
    type: nodeType,
    previousNodeId,
    previousNodeOutput,
  })
}

const handleRemoveNode = (nodeId) => {
  emit('remove-node', nodeId)
}

const handleReplaceNode = (nodeId, nodeType) => {
  emit('replace-node', nodeId, nodeType)
}
</script>
