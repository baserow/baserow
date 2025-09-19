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
      @add-node="
        emit('add-node', {
          type: $event,
          previousNodeId: node.id,
          previousNodeOutput: edge.uid,
        })
      "
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
    />
  </div>
</template>

<script setup>
import { useStore, inject } from '@nuxtjs/composition-api'
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

const emit = defineEmits([
  'add-node',
  'select-node',
  'remove-node',
  'replace-node',
])

const store = useStore()
const workflow = inject('workflow')

const nextNodesOnEdge = store.getters['automationWorkflowNode/getNextNodes'](
  workflow.value,
  props.node,
  props.edge.uid
)
</script>
