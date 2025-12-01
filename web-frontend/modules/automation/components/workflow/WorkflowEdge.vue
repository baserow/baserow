<template>
  <div class="workflow-edge">
    <div v-if="hasSiblings" class="workflow-edge__label">{{ edgeLabel }}</div>
    <div
      class="workflow-edge__dropzone-wrapper"
      :class="{
        'workflow-edge__dropzone-wrapper--with-next': nextNodesOnEdge.length,
      }"
    >
      <div
        v-if="draggingNodeId && !isDropZoneDisabled"
        class="workflow-edge__dropzone"
        :class="{
          'workflow-edge__dropzone--hover': isDragOver,
        }"
        @dragover.prevent
        @dragenter="handleDragEnter"
        @dragleave="handleDragLeave"
        @drop="handleDrop"
      />
      <WorkflowAddBtnNode
        data-highlight="automation-add-node-btn"
        class="workflow-edge__add-button"
        :class="{
          'workflow-edge__add-button--hover': isDragOver,
          'workflow-edge__add-button--active':
            draggingNodeId && !isDropZoneDisabled,
        }"
        :disabled="readOnly"
        @add-node="
          emit('add-node', {
            type: $event,
            position: isChild ? 'child' : 'south',
            output: edgeUid,
            referenceNode: node,
          })
        "
      />
    </div>

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
      @move-node="emit('move-node', $event)"
      @duplicate-node="emit('duplicate-node', $event)"
    />
  </div>
</template>

<script setup>
import { useStore, inject, computed, ref } from '@nuxtjs/composition-api'
import WorkflowNode from '@baserow/modules/automation/components/workflow/WorkflowNode'

import WorkflowAddBtnNode from '@baserow/modules/automation/components/workflow/WorkflowAddBtnNode'

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  edgeUid: { type: String, default: '' },
  edgeLabel: { type: String, default: '' },
  isChild: {
    type: Boolean,
    default: false,
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
  'move-node',
  'remove-node',
  'replace-node',
  'duplicate-node',
])

const store = useStore()
const workflow = inject('workflow')
const isDragOver = ref(false)

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

  // Disable drop zone immediately below the dragged node.
  if (props.node.id === draggedNode.value.id) {
    return true
  }

  if (
    nextNodesOnEdge.value.map(({ id }) => id).includes(draggedNode.value.id)
  ) {
    // the dragged node is already the next node
    return true
  }

  const ancestors = store.getters['automationWorkflowNode/getAncestors'](
    workflow.value,
    props.node
  ).map(({ id }) => id)

  if (ancestors.includes(draggedNode.value.id)) {
    // We can't include a container in itself
    return true
  }

  return false
})

const handleDragEnter = () => {
  isDragOver.value = true
}
const handleDragLeave = () => {
  isDragOver.value = false
}

const handleDrop = () => {
  isDragOver.value = false

  emit('move-node', {
    referenceNodeId: props.node.id,
    position: props.isChild ? 'child' : 'south',
    output: props.edgeUid,
  })
}

const nextNodesOnEdge = computed(() => {
  if (!props.isChild) {
    return store.getters['automationWorkflowNode/getNextNodes'](
      workflow.value,
      props.node,
      props.edgeUid
    )
  } else {
    // we are selecting children
    return store.getters['automationWorkflowNode/getChildren'](
      workflow.value,
      props.node
    )
  }
})
</script>
