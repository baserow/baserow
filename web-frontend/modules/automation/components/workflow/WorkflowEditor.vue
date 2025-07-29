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
const NODE_VERTICAL_SPACING = 144 // Vertical distance between the tops of consecutive data nodes
const ADD_BUTTON_OFFSET_Y = 92 // Vertical offset of add button relative to the data node above it
const INITIAL_Y_POS = 0
const DATA_NODE_X_POS = 0
const DATA_NODE_WIDTH = 380 // How wide is a node?
const DATA_NODE_MIDDLE = DATA_NODE_WIDTH / 2 // The middle of a node.

watch(
  selectedNodeId,
  (newId) => {
    if (newId) addSelectedNodes([{ id: newId.toString() }])
  },
  { immediate: true }
)

/**
 * When the component is mounted, we emit the first node's ID. This is
 * to ensure that the first node (the trigger) is selected by default.
 */
onMounted(() => {
  emit('input', props.nodes[0].id)
})

const automation = inject('automation')
const displayNodes = computed(() => {
  const vueFlowNodes = []
  const sortedDataNodes = [...props.nodes]

  if (sortedDataNodes.length > 0) {
    let currentY = INITIAL_Y_POS

    sortedDataNodes.forEach((dataNode, index) => {
      const nextDataNode = sortedDataNodes[index + 1]
      const nodeType = app.$registry.get('node', dataNode.type)
      const nodeEdges = nodeType.getNodeEdges({ node: dataNode })

      // By default, the `x` position is set to the current
      // value of DATA_NODE_X_POS.
      let positionX = DATA_NODE_X_POS

      // However... if we have a previous node (which all nodes do, except the trigger),
      // we'll need to adjust the `x` position to be the same as the previous node's
      // add button's position. This is to ensure that the nodes are aligned correctly.
      const previousNode = sortedDataNodes.find((node) => {
        return node.id === dataNode.previous_node_id
      })
      const previousNodeAddButton = vueFlowNodes.find((node) => {
        return (
          node.type === 'workflow-add-button-node' &&
          node.data.outputUid === dataNode.previous_node_output &&
          node.data.nodeId === previousNode.id
        )
      })
      if (previousNodeAddButton) {
        positionX = previousNodeAddButton.position.x - DATA_NODE_MIDDLE
      }

      const workflowNodePosition = {
        x: positionX,
        y: currentY,
      }
      const workflowNode = {
        type: 'workflow-node',
        label: nodeType.getLabel({
          automation: automation.value,
          node: dataNode,
        }),
        id: dataNode.id.toString(),
        position: workflowNodePosition,
        data: {
          nodeId: dataNode.id,
          position: workflowNodePosition,
          isTrigger: nodeType.isTrigger,
          readOnly: workflowReadOnly.value,
          debug: workflowDebug.value,
          outputUid: dataNode.previous_node_output,
        },
      }
      vueFlowNodes.push(workflowNode)

      // If we have more than one edge, then bump the Y position,
      // otherwise we're quite close to the router node above it.
      if (nodeEdges.length > 1) {
        currentY += NODE_VERTICAL_SPACING / 2
      }
      nodeEdges.forEach((edge) => {
        // When we want to position the add button's `x` position, we need to consider
        // if the edge has an `uid` or not. If it does, we use the edge's position, as
        // the edges are pre-configured with positions, and we want to use those values.
        // Note however that the edge's `x` position is relative to the node's position,
        // that way when the node itself is position *off the x axis*, the edge's position
        // is still correct.
        // If there's no `uid`, then it's a straightforward edge between non-branches nodes,
        // and we can use the node's position
        const positionX = edge.position.x
          ? edge.position.x + workflowNode.position.x
          : workflowNode.position.x
        vueFlowNodes.push({
          id: `add-button-${dataNode.id}-${edge.uid}`,
          type: 'workflow-add-button-node',
          position: {
            x: positionX + DATA_NODE_MIDDLE,
            y: currentY + ADD_BUTTON_OFFSET_Y,
          },
          data: {
            nodeId: dataNode.id,
            outputUid: edge.uid,
            debug: workflowDebug.value,
            disabled: props.isAddingNode || workflowReadOnly.value,
          },
        })
      })

      // Inspect the next data node. If it has a different previous_node_id,
      // we need to bump the Y position to ensure that the next node sits below
      // the current one. If the next node has the same previous_node_id, then
      // we can keep the current Y position as they're from the same branch.
      if (
        nextDataNode &&
        dataNode.previous_node_id !== nextDataNode.previous_node_id
      ) {
        currentY += NODE_VERTICAL_SPACING
      }
    })
  }
  return vueFlowNodes
})

const store = useStore()
const workflow = inject('workflow')
const computedEdges = computed(() => {
  const edges = []
  const currentNodesToProcess = displayNodes.value

  const processNode = (sourceDataNode) => {
    const sourceDataNodeType = app.$registry.get('node', sourceDataNode.type)
    sourceDataNodeType
      .getNodeEdges({ node: sourceDataNode })
      .forEach((edge, edgeIndex) => {
        const targetDataNodes = store.getters[
          'automationWorkflowNode/getNextNodes'
        ](workflow.value, sourceDataNode, edge.uid)

        // Add the edge between `sourceDataNode` and the *add button* node.
        const addButtonBelow = currentNodesToProcess.find((node) => {
          // If a node has an outputUid, then we're looking for an add button
          // associated with that branch.
          if (node.data.outputUid) {
            return (
              node.data.outputUid === edge.uid &&
              node.type === 'workflow-add-button-node'
            )
          } else {
            // If a node does not have an outputUid, then we're looking for an add button
            // that has the same nodeId as the sourceDataNode.
            return (
              node.data.nodeId === sourceDataNode.id &&
              node.type === 'workflow-add-button-node'
            )
          }
        })
        edges.push({
          id: `e-${workflowDebug.value}-${sourceDataNode.id}-${addButtonBelow.id}-${edge.uid}`,
          source: sourceDataNode.id.toString(),
          target: addButtonBelow.id.toString(),
          data: { outputUid: edge.uid },
          label: workflowDebug.value
            ? `from:${sourceDataNode.id} to:addBtn${edgeIndex}`
            : edge.label,
          type: 'smoothstep',
        })

        // If there are nodes *after* `sourceDataNode`, we need to:
        // 1. Create an edge between `addButtonBelow` and each of those nodes.
        // 2. Process each of those nodes to create edges between them and their own add buttons.
        // 3. Recursively process each of those nodes to find their own target data nodes.
        if (targetDataNodes.length) {
          for (const targetDataNode of targetDataNodes) {
            // An edge between two data nodes OR a data node and an add button.
            const source = addButtonBelow || sourceDataNode
            edges.push({
              id: `e-${workflowDebug.value}-${source.id}-${targetDataNode.id}`,
              source: source.id.toString(),
              target: targetDataNode.id.toString(),
              data: { outputUid: edge.uid },
              type: 'smoothstep',
              label: workflowDebug.value
                ? `from:${source.id} to:${targetDataNode.id}`
                : '',
            })
            processNode(targetDataNode)
          }
        }
      })
  }

  const triggerNode = currentNodesToProcess.find((node) => node.data.isTrigger)
  const triggerDataNode = props.nodes.find(
    (node) => node.id === triggerNode.data.nodeId
  )
  processNode(triggerDataNode)

  return edges
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
