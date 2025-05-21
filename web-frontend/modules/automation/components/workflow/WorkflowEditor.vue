<template>
  <VueFlow
    :nodes="displayNodes"
    :edges="computedEdges"
    class="basic-flow"
    :zoom-on-scroll="false"
    :nodes-draggable="nodesDraggable"
    :zoom-on-drag="zoomOnScroll"
    :pan-on-scroll="panOnScroll"
    :zoom-on-double-click="zoomOnDoubleClick"
  >
    <Background pattern-color="#ededed" :size="3" :gap="15" />
    <template #node-workflow-node="slotProps">
      <WorkflowNode
        :id="slotProps.id"
        :label="slotProps.label"
        :selected="slotProps.selected"
        :dragging="slotProps.dragging"
        :position="slotProps.position"
        :data="slotProps.data"
        @removeNode="handleRemoveNode"
      />
    </template>

    <template #node-workflow-add-button-node="slotProps">
      <WorkflowAddBtnNode
        :id="slotProps.id"
        :data="slotProps.data"
        :label="slotProps.label"
        :selected="slotProps.selected"
        :dragging="slotProps.dragging"
        :position="slotProps.position"
        @addNode="handleAddNode"
      />
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
import { ref, computed } from 'vue'
import WorkflowNode from '@baserow/modules/automation/components/workflow/WorkflowNode.vue'
import WorkflowAddBtnNode from '@baserow/modules/automation/components/workflow/WorkflowAddBtnNode.vue'
import WorkflowEdge from '@baserow/modules/automation/components/workflow/WorkflowEdge.vue'

const props = defineProps({
  nodes: {
    type: Array,
    required: true,
  },
  readOnly: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['add-node'])

const { onInit } = useVueFlow()

const nodesDraggable = ref(false)
const zoomOnScroll = ref(false)
const panOnScroll = ref(true)
const zoomOnDoubleClick = ref(false)

// Constants for positioning
const NODE_VERTICAL_SPACING = 144 // Vertical distance between the tops of consecutive data nodes
const ADD_BUTTON_OFFSET_Y = 92 // Vertical offset of add button relative to the data node above it
const INITIAL_Y_POS = 0
const DATA_NODE_X_POS = 0
const ADD_BUTTON_X_POS = 190

const displayNodes = computed(() => {
  const vueFlowNodes = []
  // props.nodes should already be sorted by 'order' from the store getter
  const sortedDataNodes = [...props.nodes]

  if (props.readOnly) {
    let currentY = INITIAL_Y_POS
    return sortedDataNodes.map((node) => {
      const position = { x: DATA_NODE_X_POS, y: currentY }
      currentY += NODE_VERTICAL_SPACING // Increment Y for the next node

      return {
        ...node,
        id: node.id.toString(), // VueFlow expects string IDs
        position,
        type: 'workflow-node',
        data: { readOnly: props.readOnly },
      }
    })
  }

  // Not readOnly mode: intersperse workflow-add-button-node nodes
  if (sortedDataNodes.length === 0) {
    // No data nodes, show a single add button to start the flow
    vueFlowNodes.push({
      id: 'initial-workflow-add-button-node',
      type: 'workflow-add-button-node',
      label: '',
      position: { x: ADD_BUTTON_X_POS, y: ADD_BUTTON_OFFSET_Y },
      data: { nodeId: null }, // No preceding data node
    })
  } else {
    let currentY = INITIAL_Y_POS
    sortedDataNodes.forEach((dataNode) => {
      const dataNodePosition = { x: DATA_NODE_X_POS, y: currentY }
      vueFlowNodes.push({
        ...dataNode,
        type: 'workflow-node',
        id: dataNode.id.toString(),
        position: dataNodePosition,
        data: { readOnly: props.readOnly },
      })

      // Add an Add Node Button node below it
      const addButtonPosition = {
        x: ADD_BUTTON_X_POS,
        y: currentY + ADD_BUTTON_OFFSET_Y,
      }

      vueFlowNodes.push({
        id: `workflow-add-button-node-${dataNode.id}`,
        data: { nodeId: dataNode.id },
        type: 'workflow-add-button-node',
        position: addButtonPosition,
      })

      // Increment Y for the next node
      currentY += NODE_VERTICAL_SPACING
    })
  }
  return vueFlowNodes
})

const computedEdges = computed(() => {
  const edges = []
  const currentNodesToProcess = displayNodes.value

  if (props.readOnly) {
    const dataNodesOnly = displayNodes.value
    for (let i = 0; i < dataNodesOnly.length - 1; i++) {
      const sourceNode = dataNodesOnly[i]
      const targetNode = dataNodesOnly[i + 1]
      edges.push({
        id: `e-${sourceNode.id}-${targetNode.id}`,
        source: sourceNode.id,
        target: targetNode.id,
        type: 'workflow-edge',
      })
    }
  } else {
    for (let i = 0; i < currentNodesToProcess.length - 1; i++) {
      const source = currentNodesToProcess[i]
      const target = currentNodesToProcess[i + 1]

      edges.push({
        id: `e-${source.id}-${target.id}`,
        source: source.id,
        target: target.id,
        type: 'workflow-edge',
      })
    }
  }
  return edges
})

onInit((vueFlowInstance) => {
  vueFlowInstance.fitView({ maxZoom: 1, minZoom: 0.5 })
})

const handleAddNode = (previousNodeId) => {
  emit('add-node', {
    type: 'workflow-node',
    previousNodeId,
  })
}

const handleRemoveNode = (nodeId) => {
  emit('remove-node', nodeId)
}
</script>
