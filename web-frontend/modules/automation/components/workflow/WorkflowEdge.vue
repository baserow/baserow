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
        @add-node="handleAddNode"
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
import { useStore } from 'vuex'
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

// The dropzone and the add button both sit at the head of this edge, so an
// insertion means "before the first node currently on the edge" (a 'north' move).
// The backend derives the correct edge/output from the reference node's position,
// so output is '' for north. When the edge is empty we attach directly to this
// node on its own edge.
const resolveHeadTarget = () => {
  const firstNodeOnEdge = nextNodesOnEdge.value[0]
  if (firstNodeOnEdge) {
    return { referenceNode: firstNodeOnEdge, position: 'north', output: '' }
  }
  return {
    referenceNode: props.node,
    position: props.isChild ? 'child' : 'south',
    output: props.edgeUid,
  }
}

const handleDrop = () => {
  isDragOver.value = false

  const { referenceNode, position, output } = resolveHeadTarget()
  emit('move-node', {
    referenceNodeId: referenceNode.id,
    position,
    output,
  })
}

const handleAddNode = (type) => {
  const { referenceNode, position, output } = resolveHeadTarget()
  emit('add-node', { type, referenceNode, position, output })
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
