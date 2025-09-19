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
      <WorkflowNode
        :key="updateKey"
        :node="trigger"
        :debug="workflowDebug"
        :read-only="workflowReadOnly"
        :selected-node-id="selectedNodeId"
        @add-node="emit('add-node', $event)"
        @remove-node="emit('remove-node', $event)"
        @replace-node="emit('replace-node', $event)"
        @select-node="emit('input', $event.id)"
      />
    </template>
  </VueFlow>
</template>

<script setup>
import { VueFlow, useVueFlow } from '@vue2-flow/core'
import { Background } from '@vue2-flow/background'
import { Controls } from '@vue2-flow/controls'
import { ref, watch, toRefs, onMounted } from 'vue'
import { inject, computed } from '@nuxtjs/composition-api'
import WorkflowNode from '@baserow/modules/automation/components/workflow/WorkflowNode'

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

const vueFlowEdges = []

const emit = defineEmits(['add-node', 'remove-node', 'input'])

const { onPaneClick } = useVueFlow()

const { value: selectedNodeId } = toRefs(props)

const zoomOnScroll = ref(false)
const panOnScroll = ref(true)
const zoomOnDoubleClick = ref(false)
const updateKey = ref(1)

const trigger = computed(() => {
  return props.nodes.find((node) => node.previous_node_id === null)
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

const workflowDebug = inject('workflowDebug')
const workflowReadOnly = inject('workflowReadOnly')

const computedNodes = computed(() => {
  return props.nodes
})

/**
 * This watcher is used to force the update the workflow graph when nodes are updated.
 *  Vue-flow prevents the update somehow.
 */
watch(
  computedNodes,
  () => {
    updateKey.value += 1
  },
  { deep: true }
)

/**
 * When the component is mounted, we emit the first node's ID. This is
 * to ensure that the first node (the trigger) is selected by default.
 */
onMounted(() => {
  emit('input', props.nodes[0].id)
})

/**
 * When the pane is clicked, we emit `null` which
 * clears the selected node in the node store.
 */
onPaneClick(() => {
  emit('input', null)
})
</script>
