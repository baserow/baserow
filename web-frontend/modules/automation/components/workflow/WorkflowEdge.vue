<template>
  <div class="workflow-edge">
    <div v-if="hasSiblings" class="workflow-edge__label">{{ edge.label }}</div>
    <WorkflowAddBtnNode
      class="workflow-edge__add-button"
      :class="{
        'workflow-edge__add-button--with-next': nextNodesOnEdge.length,
      }"
      :disabled="readOnly"
      :debug="debug"
      :disabled-drop="isDropZoneDisabled"
      @add-node="
        emit('add-node', {
          type: $event,
          previousNodeId: node.id,
          previousNodeOutput: edge.uid,
        })
      "
      @move-node="
        emit('move-node', { afterNodeId: node.id, afterNodeOutput: edge.uid })
      "
      @toggle-pan="emit('toggle-pan', $event)"
    />

    <WorkflowNode
      v-for="nextNode in nextNodesOnEdge"
      :key="nextNode.id"
      :node="nextNode"
      :selected-node-id="selectedNodeId"
      :debug="debug"
      :read-only="readOnly"
      @add-node="emit('add-node', $event)"
      @select-node="emit('select-node', $event)"
      @remove-node="emit('remove-node', $event)"
      @replace-node="emit('replace-node', $event)"
      @toggle-pan="emit('toggle-pan', $event)"
      @move-node="emit('move-node', $event)"
    />
  </div>
</template>

<script setup>
import { useStore, inject, computed } from '@nuxtjs/composition-api'
import WorkflowNode from '@baserow/modules/automation/components/workflow/WorkflowNode'

import WorkflowAddBtnNode from '@baserow/modules/automation/components/workflow/WorkflowAddBtnNode'

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  edge: {
    type: Object,
    required: true,
  },
  hasSiblings: {
    type: Boolean,
    default: false,
  },
  selectedNodeId: {
    type: Number,
    required: false,
    default: null,
  },
  debug: {
    type: Boolean,
    default: false,
  },
  readOnly: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['add-node', 'select-node', 'move-node'])

const store = useStore()
const workflow = inject('workflow')

const draggingNodeId = computed(
  () => store.getters['automationWorkflowNode/getDraggingNodeId']
)

const draggedNode = computed(() => {
  if (!draggingNodeId.value) return null
  return store.getters['automationWorkflowNode/findById'](
    workflow.value,
    draggingNodeId.value
  )
})

const isDropZoneDisabled = computed(() => {
  if (!draggedNode.value) {
    return false
  }

  const afterNodeId = props.node.id
  const afterNodeOutput = props.edge.uid

  // Disable drop zone immediately below the dragged node.
  if (afterNodeId === draggedNode.value.id) {
    return true
  }

  // Disable drop zone where the dragged node is currently located.
  if (
    draggedNode.value.previous_node_id === afterNodeId &&
    draggedNode.value.previous_node_output === afterNodeOutput
  ) {
    return true
  }

  return false
})

const nextNodesOnEdge = store.getters['automationWorkflowNode/getNextNodes'](
  workflow.value,
  props.node,
  props.edge.uid
)
</script>
