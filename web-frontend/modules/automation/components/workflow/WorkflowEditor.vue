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

// Constants for positioning
const DATA_NODE_WIDTH = 412 // How wide is a node?
const DATA_NODE_MIDDLE = DATA_NODE_WIDTH / 2 // The middle of a node.
const NODE_PADDING = 30 // Padding between node edges

watch(
  selectedNodeId,
  (newId) => {
    if (newId) addSelectedNodes([{ id: newId.toString() }])
  },
  { immediate: true }
)

const calculateNodeDimensions = (node) => {
  const nodeType = app.$registry.get('node', node.type)
  const nextNodes = store.getters['automationWorkflowNode/getNextNodes'](
    workflow.value,
    node
  )

  // First recursively compute next node dimension
  const nextNodeDimensions = Object.assign(
    {},
    ...nextNodes.map((nextNode) => calculateNodeDimensions(nextNode))
  )

  // Then we compute the edge dimensions
  const nodeEdges = nodeType.getNodeEdges({ node })

  const edgeDimensions = Object.assign(
    {},
    ...nodeEdges.map((edge) => {
      const nextNodesOnEdge = store.getters[
        'automationWorkflowNode/getNextNodes'
      ](workflow.value, node, edge.uid)

      if (nextNodesOnEdge.length) {
        const width = _.sum(
          nextNodesOnEdge.map(
            (nextNode) =>
              nextNodeDimensions[nextNode.id].width +
              (nextNodesOnEdge.length - 1) * NODE_PADDING
          )
        )

        // We compute the position of the input by taking the middle between the first
        // and the last input
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
      // The default width if we have no nodes on the edge.
      return { [edge.uid]: { width: 100, input: 50 } }
    })
  )

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

  const edgesHeight = nodeEdges.length > 1 ? 120 : 100 // or something like that
  const nodeHeight = 72 /* We can deal with child node here later */
  const height = edgesHeight + nodeHeight

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

const calculatePositions = (dimensions, node, { x = 0, y = 0 } = {}) => {
  const nodeType = app.$registry.get('node', node.type)

  let currentEdgeX = x - dimensions[node.id].outputLeft + DATA_NODE_MIDDLE
  let currentX = x - dimensions[node.id].outputLeft // As input is the number of pixel from the left

  const nodeEdges = nodeType.getNodeEdges({ node })
  const oneEdge = nodeEdges.length === 1

  const addButtonPositions = []
  const edges = []

  const nextNodePositions = Object.assign(
    {},
    ...nodeEdges.map((edge, edgeIndex) => {
      const nextNodesAlongEdge = store.getters[
        'automationWorkflowNode/getNextNodes'
      ](workflow.value, node, edge.uid)

      const noNodeOnEdge = nextNodesAlongEdge.length === 0

      const buttonKey = `edge-${node.id}-${edge.uid || 'default'}`

      // add edge between node and add button
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

      const edgeWidth = dimensions[node.id].edges[edge.uid].width

      // We define the position of the buttons
      addButtonPositions.push({
        uid: edge.uid,
        key: buttonKey,
        x:
          currentEdgeX -
          16 + // half an add button width
          dimensions[node.id].edges[edge.uid].input,
        y: y + (oneEdge ? 90 : 130),
      })

      if (noNodeOnEdge) {
        // The currentX didn't change as we have no node but it has to increase
        currentX += edgeWidth + NODE_PADDING
      }
      currentEdgeX += edgeWidth + NODE_PADDING

      const nodesAlongEdgePositions = Object.assign(
        {},
        ...nextNodesAlongEdge.map((nextNode) => {
          // Add edge between add button and next node
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

          const nextX = currentX + dimensions[nextNode.id].input // The next X is the input position of the next node
          const nextY = y + dimensions[node.id].height
          currentX += dimensions[nextNode.id].width + NODE_PADDING // Moving to next node

          return calculatePositions(dimensions, nextNode, {
            x: nextX,
            y: nextY,
          })
        })
      )

      return nodesAlongEdgePositions
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
