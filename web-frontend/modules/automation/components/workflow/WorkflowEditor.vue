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
const ADD_BUTTON_OFFSET_Y = 85 // Vertical offset of add button relative to the data node above it
const DATA_NODE_WIDTH = 412 // How wide is a node?
const DATA_NODE_MIDDLE = DATA_NODE_WIDTH / 2 // The middle of a node.

watch(
  selectedNodeId,
  (newId) => {
    if (newId) addSelectedNodes([{ id: newId.toString() }])
  },
  { immediate: true }
)

const calculateNodeDimensions = (node, level = 0) => {
  const nodeType = app.$registry.get('node', node.type)
  const nextNodes = store.getters['automationWorkflowNode/getNextNodes'](
    workflow.value,
    node
  )

  const nextNodeDimensions = nextNodes.map((nextNode) =>
    calculateNodeDimensions(nextNode, level + 1)
  )
  const merged = Object.assign({}, ...nextNodeDimensions)

  const nodeEdges = nodeType.getNodeEdges({ node })
  const edgeDimensions = nodeEdges.map((edge) => {
    const nextNodesOnEdge = store.getters[
      'automationWorkflowNode/getNextNodes'
    ](workflow.value, node, edge.uid)

    if (nextNodesOnEdge.length) {
      const width = _.sum(
        nextNodesOnEdge.map((nextNode) => merged[nextNode.id].width)
      )

      const leftMost = merged[nextNodesOnEdge[0].id]
      const rightMost = merged[nextNodesOnEdge.at(-1).id]
      const edgeWidth =
        width - leftMost.input - (rightMost.width - rightMost.input)

      return {
        [edge.uid]: {
          width,
          input: leftMost.input + edgeWidth / 2,
        },
      }
      // TODO: fix the input computation, the input isn't in the middle
    }
    // The default width if we have no nodes on the edge.
    return { [edge.uid]: { width: 200, input: 100 } }
  })

  const mergedEdgeDimensions = Object.assign({}, ...edgeDimensions)

  const widthSum = _.sum(
    nodeEdges.map((edge) => mergedEdgeDimensions[edge.uid].width)
  )
  const width = Math.max(widthSum, DATA_NODE_WIDTH)

  const leftMost = mergedEdgeDimensions[nodeEdges[0].uid]
  const rightMost = mergedEdgeDimensions[nodeEdges.at(-1).uid]
  const edgesWidth =
    width - leftMost.input - (rightMost.width - rightMost.input)

  const input = leftMost.input + edgesWidth / 2
  // const input = width / 2

  const edgesHeight = 150 // or something like that
  const nodeHeight = 72 /* We can deal with child node here later */
  const height = edgesHeight + nodeHeight

  return {
    ...merged,
    ...{
      [node.id]: {
        width,
        height,
        input,
        edges: mergedEdgeDimensions,
      },
    },
  }
}

const calculatePositions = (dimensions, node, { x = 0, y = 0 } = {}) => {
  const nodeType = app.$registry.get('node', node.type)

  let currentEdgeX = x - dimensions[node.id].input
  let currentX = x - dimensions[node.id].input // As input is the number of pixel from the left
  const nodeEdges = nodeType.getNodeEdges({ node })
  const addButtonPositions = []
  const nextNodePositions = nodeEdges.map((edge, index) => {
    const nextNodesAlongEdge = store.getters[
      'automationWorkflowNode/getNextNodes'
    ](workflow.value, node, edge.uid)

    const nodesAlongEdgePositions = nextNodesAlongEdge.map((nextNode) => {
      const nextX = currentX + dimensions[nextNode.id].input // The next X is the input position of the next node
      const nextY = y + dimensions[node.id].height
      currentX += dimensions[nextNode.id].width // Going to next node
      return calculatePositions(dimensions, nextNode, {
        x: nextX,
        y: nextY,
      })
    })

    if (nodesAlongEdgePositions.length === 0) {
      currentX += DATA_NODE_WIDTH
    }

    const edgeWidth = dimensions[node.id].edges[edge.uid].width
    addButtonPositions.push({
      uid: edge.uid,
      key: `edge-${node.id}-${edge.uid || 'default'}`,
      x:
        currentEdgeX -
        15 + // half an add button width
        dimensions[node.id].edges[edge.uid].input +
        DATA_NODE_MIDDLE,
      y:
        nodeEdges.length > 1
          ? y + ADD_BUTTON_OFFSET_Y * 2
          : y + ADD_BUTTON_OFFSET_Y,
    })

    currentEdgeX += edgeWidth

    return Object.assign({}, ...nodesAlongEdgePositions)
  })

  const merged = Object.assign({}, ...nextNodePositions)

  return {
    ...merged,
    [node.id]: {
      x,
      y,
      addButtonPositions,
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
const displayNodes = computed(() => {
  const vueFlowNodes = []
  const sortedDataNodes = [...props.nodes]

  const trigger = sortedDataNodes.find((node) => node.previous_node_id === null)
  const dimensions = calculateNodeDimensions(trigger)
  console.log('calculated dimensions', dimensions)
  const positions = calculatePositions(dimensions, trigger)
  console.log('positions before looping', positions)

  if (sortedDataNodes.length > 0) {
    sortedDataNodes.forEach((dataNode) => {
      const nodeType = app.$registry.get('node', dataNode.type)

      vueFlowNodes.push({
        type: 'workflow-node',
        label: nodeType.getLabel({
          automation: automation.value,
          node: dataNode,
        }),
        id: dataNode.id.toString(),
        position: positions[dataNode.id],
        data: {
          nodeId: dataNode.id,
          isTrigger: nodeType.isTrigger,
          readOnly: workflowReadOnly.value,
          debug: workflowDebug.value,
          outputUid: dataNode.previous_node_output,
        },
      })

      console.log(
        'before positions addButtonPositions ',
        dataNode.id,
        structuredClone(positions)
      )
      positions[dataNode.id].addButtonPositions.forEach((addButtonPosition) => {
        vueFlowNodes.push({
          id: addButtonPosition.key,
          type: 'workflow-add-button-node',
          position: addButtonPosition,
          data: {
            nodeId: dataNode.id,
            outputUid: addButtonPosition.uid,
            debug: workflowDebug.value,
            disabled: props.isAddingNode || workflowReadOnly.value,
          },
        })
      })
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
