<template>
  <VueFlow
    class="workflow-editor"
    :nodes="displayNodes"
    :edges="computedEdges"
    :zoom-on-scroll="false"
    :nodes-draggable="nodesDraggable"
    :zoom-on-drag="zoomOnScroll"
    :pan-on-scroll="panOnScroll"
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
        @removeNode="handleRemoveNode"
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
      <CreateWorkflowNodeContext
        :ref="`createNodeContext-${slotProps.id}`"
        :last-node-id="slotProps.data.nodeId"
        @change="createNode"
      ></CreateWorkflowNodeContext>
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
import { ref, computed, watch, toRefs } from 'vue'
import {
  inject,
  useContext,
  nextTick,
  getCurrentInstance,
} from '@nuxtjs/composition-api'
import WorkflowNode from '@baserow/modules/automation/components/workflow/WorkflowNode'
import WorkflowAddBtnNode from '@baserow/modules/automation/components/workflow/WorkflowAddBtnNode'
import WorkflowEdge from '@baserow/modules/automation/components/workflow/WorkflowEdge'
import CreateWorkflowNodeContext from '@baserow/modules/automation/components/workflow/CreateWorkflowNodeContext'

const props = defineProps({
  nodes: {
    type: Array,
    required: true,
  },
  readOnly: {
    type: Boolean,
    default: false,
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

const nodesDraggable = ref(false)
const zoomOnScroll = ref(false)
const panOnScroll = ref(true)
const zoomOnDoubleClick = ref(false)

// Constants for positioning
const NODE_VERTICAL_SPACING = 144 // Vertical distance between the tops of consecutive data nodes
const ADD_BUTTON_OFFSET_Y = 92 // Vertical offset of add button relative to the data node above it
const INITIAL_ADD_BUTTON_OFFSET_Y = 52
const INITIAL_Y_POS = 0
const DATA_NODE_X_POS = 0
const ADD_BUTTON_X_POS = 190

watch(
  selectedNodeId,
  (newId) => {
    if (newId) addSelectedNodes([{ id: newId.toString() }])
  },
  { immediate: true }
)

const automation = inject('automation')
const displayNodes = computed(() => {
  const vueFlowNodes = []
  // props.nodes should already be sorted by 'order' from the store getter
  const sortedDataNodes = [...props.nodes]

  if (props.readOnly) {
    let currentY = INITIAL_Y_POS
    return sortedDataNodes.map((node) => {
      const position = { x: DATA_NODE_X_POS, y: currentY }
      currentY += NODE_VERTICAL_SPACING // Increment Y for the next node
      const nodeType = app.$registry.get('node', node.type)

      return {
        ...node,
        id: node.id.toString(), // VueFlow expects string IDs
        position,
        type: 'workflow-node',
        data: { readOnly: props.readOnly, isTrigger: nodeType.isTrigger },
      }
    })
  }

  // Not readOnly mode: intersperse workflow-add-button-node nodes
  if (!workflowHasTrigger.value) {
    // No nodes, show a single add button to start the flow
    vueFlowNodes.push({
      id: 'initial-workflow-add-button-node',
      type: 'workflow-add-button-node',
      label: '',
      position: {
        x: ADD_BUTTON_X_POS,
        y: INITIAL_Y_POS - INITIAL_ADD_BUTTON_OFFSET_Y,
      },
      data: { nodeId: null, disabled: props.isAddingNode }, // No preceding data node
    })
  }

  if (sortedDataNodes.length > 0) {
    let currentY = INITIAL_Y_POS
    sortedDataNodes.forEach((dataNode) => {
      const dataNodePosition = { x: DATA_NODE_X_POS, y: currentY }
      const nodeType = app.$registry.get('node', dataNode.type)
      vueFlowNodes.push({
        ...dataNode,
        type: 'workflow-node',
        label: nodeType.getLabel({
          automation: automation.value,
          node: dataNode,
        }),
        id: dataNode.id.toString(),
        position: dataNodePosition,
        data: {
          readOnly: props.readOnly,
          isTrigger: nodeType.isTrigger,
          isInError: nodeType.isInError({ service: dataNode.service }),
        },
      })

      // Add an Add Node Button node below it
      const addButtonPosition = {
        x: ADD_BUTTON_X_POS,
        y: currentY + ADD_BUTTON_OFFSET_Y,
      }

      vueFlowNodes.push({
        id: `workflow-add-button-node-${dataNode.id}`,
        data: { nodeId: dataNode.id, disabled: props.isAddingNode },
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

onPaneClick(() => {
  emit('input', null)
})

onNodeClick(({ node }) => {
  if (node.type === 'workflow-node') {
    emit('input', node.id)
  }
})

const workflowHasTrigger = computed(() => {
  return props.nodes.some((node) => {
    const nodeType = app.$registry.get('node', node.type)
    return nodeType.isTrigger
  })
})

const activeCreateNodeContext = ref(null)

// Hide the active node create context when user pan the canvas
onMove(() => {
  activeCreateNodeContext.value?.hide()
})

const toggleCreateContext = async (nodeId) => {
  await nextTick()
  const nodeContext = refs[`createNodeContext-${nodeId}`]
  activeCreateNodeContext.value = nodeContext
  const nodeAddBtn = refs[`addWorkflowBtnNode-${nodeId}`]
  nodeContext.show(nodeAddBtn.$el, 'bottom', 'left', 10, -225)
}

const createNode = (nodeType, previousNodeId) => {
  emit('add-node', {
    type: nodeType,
    previousNodeId,
  })
}

const handleRemoveNode = (nodeId) => {
  emit('remove-node', nodeId)
}
</script>
