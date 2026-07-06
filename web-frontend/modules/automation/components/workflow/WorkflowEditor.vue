<template>
  <VueFlow
    class="workflow-editor"
    :nodes="vueFlowNodes"
    :edges="vueFlowEdges"
    :zoom-on-scroll="false"
    :nodes-draggable="false"
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

    <template #node-workflow-node>
      <div v-if="trigger">
        <WorkflowNode
          :key="updateKey"
          :node="trigger"
          :debug="workflowDebug"
          :read-only="readOnly"
          :selected-node-id="selectedNodeId"
          @add-node="emit('add-node', $event)"
          @remove-node="emit('remove-node', $event)"
          @replace-node="emit('replace-node', $event)"
          @select-node="emit('update:modelValue', $event.id)"
          @move-node="emit('move-node', $event)"
          @duplicate-node="emit('duplicate-node', $event)"
        />
      </div>
      <template v-else>
        <div class="workflow-editor__trigger-selector" @scroll.stop>
          <h2 class="workflow-editor__trigger-selector-title">
            {{ $t('workflowEditor.chooseEvent') }}
          </h2>
          <WorkflowAddNodeMenu
            :only-trigger="true"
            @change="emit('add-node', { type: $event })"
          />
        </div>
      </template>
    </template>
  </VueFlow>
</template>

<script setup>
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { ref, computed, watch, toRef, inject, provide, onMounted } from 'vue'
import debounce from 'lodash/debounce'

import WorkflowNode from '@baserow/modules/automation/components/workflow/WorkflowNode'
import WorkflowAddNodeMenu from '@baserow/modules/automation/components/workflow/WorkflowAddNodeMenu'
import NodeGraphHandler from '@baserow/modules/automation/utils/nodeGraphHandler'
import { assignGotoMarkers } from '@baserow/modules/automation/utils/gotoMarkers'
import { isBackwardGotoJump } from '@baserow/modules/automation/utils/gotoNode'

const props = defineProps({
  nodes: {
    type: Array,
    required: true,
  },
  modelValue: {
    type: [String, Number],
    default: null,
  },
  isAddingNode: {
    type: Boolean,
    default: false,
  },
  readOnly: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:modelValue',
  'add-node',
  'remove-node',
  'replace-node',
  'move-node',
  'duplicate-node',
])

// Injected dependencies
const app = useNuxtApp()
const workflow = inject('workflow')
const workflowDebug = inject('workflowDebug')

// Vue Flow setup
const { onPaneClick } = useVueFlow()
const vueFlowEdges = []

// Local state
const zoomOnScroll = ref(false)
const panOnScroll = ref(true)
const zoomOnDoubleClick = ref(false)
const updateKey = ref(1)

// Computed properties
const selectedNodeId = toRef(props, 'modelValue')

// The goto connectors compare against numeric node ids, while `modelValue`
// can arrive as a string from the editor.
const selectedNodeIdNumber = computed(() =>
  props.modelValue == null ? null : Number(props.modelValue)
)

// Every valid jump (e.g. a "Go to node" and its destination) gets a stable
// marker letter. Rather than draw a line between the two ends, both node cards
// show the same marker so the reader can pair them by eye.
const gotoJumps = computed(() => {
  if (!workflow.value) {
    return []
  }
  return assignGotoMarkers({
    nodes: props.nodes,
    getConnectionsFor: (node) =>
      app.$registry
        .get('node', node.type)
        .getConnections({ workflow: workflow.value, node }),
  })
})

// Per-node lookup of the markers entering ("in") and leaving ("out") it,
// provided to every node card. A marker is "active" while either end of its
// jump is the selected node, so selecting one end highlights its pair.
const gotoMarkers = computed(() => {
  const selected = selectedNodeIdNumber.value
  const handler = workflow.value ? new NodeGraphHandler(workflow.value) : null
  const previousNodesOf = (node) =>
    handler
      ? handler
          .getPreviousPositions(node)
          .map(([prevNode]) => prevNode)
          .filter(Boolean)
      : []
  const byNode = {}
  const push = (nodeId, entry) => {
    ;(byNode[nodeId] = byNode[nodeId] || []).push(entry)
  }
  // Backward jumps (destination runs before the Go to node) sit above it in the
  // editor, forward jumps below. Default to backward if the graph can't be read.
  const isBackwardJump = (sourceId, destinationId) => {
    const source = handler?.getNode(sourceId)
    if (!source) return true
    return isBackwardGotoJump({
      gotoNode: source,
      destinationNode: { id: destinationId },
      previousNodesOf,
    })
  }
  for (const { sourceId, destinationId, marker } of gotoJumps.value) {
    const active = sourceId === selected || destinationId === selected
    // Each end's arrow points toward its pair. The two ends always point in
    // opposite vertical directions: for a backward jump the Go to node points up
    // to its destination and the destination points down; a forward jump flips
    // both.
    const backward = isBackwardJump(sourceId, destinationId)
    push(sourceId, {
      marker,
      direction: 'out',
      arrow: backward ? 'up' : 'down',
      active,
    })
    push(destinationId, {
      marker,
      direction: 'in',
      arrow: backward ? 'down' : 'up',
      active,
    })
  }
  return byNode
})
provide('gotoMarkers', gotoMarkers)

const trigger = computed(() => {
  if (!workflow.value?.graph) {
    return null
  }
  return new NodeGraphHandler(workflow.value).getFirstNode()
})

const vueFlowNodes = computed(() => {
  return [
    {
      id: '1',
      type: 'workflow-node',
      selectable: false,
      position: { x: 0, y: 0 },
    },
  ]
})

const computedNodes = computed(() => props.nodes)

const currentGraph = computed(() => workflow.value?.graph)

// Debounced update function
const triggerUpdate = debounce(() => {
  updateKey.value += 1
}, 500)

/**
 * These watchers are used to force the update the workflow graph when nodes are updated.
 * Vue-flow prevents the natural update.
 */
watch(
  computedNodes,
  () => {
    triggerUpdate()
  },
  { deep: true }
)

watch(
  currentGraph,
  () => {
    updateKey.value += 1
  },
  { deep: false }
)

/**
 * When the component is mounted, we emit the first node's ID. This is
 * to ensure that the first node (the trigger) is selected by default.
 */
onMounted(() => {
  if (props.nodes.length) {
    emit('update:modelValue', props.nodes[0].id)
  }
})

/**
 * When the pane is clicked, we emit `null` which
 * clears the selected node in the node store.
 */
onPaneClick(() => {
  emit('update:modelValue', null)
})
</script>
