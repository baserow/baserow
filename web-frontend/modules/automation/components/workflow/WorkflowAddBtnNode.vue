<template>
  <div class="workflow-node__dropzone-wrapper">
    <div
      :class="{
        'workflow-node__dropzone': draggingNodeId && !disabledDrop,
        'workflow-node__dropzone--hover': isDragOver,
      }"
      @dragover.prevent
      @dragenter="handleDragEnter"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    ></div>

    <ButtonFloating
      ref="btn"
      class="workflow-node__add-button"
      :class="{
        'workflow-node__add-button--hover': isDragOver,
        'workflow-node__add-button--active': draggingNodeId && !disabledDrop,
      }"
      icon="iconoir-plus"
      size="small"
      :disabled="props.disabled"
      :title="$t('workflowAddNode.displayTitle')"
      @click="toggleCreateContext"
      @mousedown.stop
    />
    <WorkflowNodeContext ref="context" @change="emit('add-node', $event)" />
  </div>
</template>

<script setup>
import WorkflowNodeContext from '@baserow/modules/automation/components/workflow/WorkflowNodeContext'
import { ref, computed, useStore } from '@nuxtjs/composition-api'
import { useVueFlow } from '@vue2-flow/core'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false,
  },
  disabledDrop: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['add-node', 'move-node', 'toggle-pan'])
const store = useStore()
const isDragOver = ref(false)
const context = ref()
const btn = ref()
const draggingNodeId = computed(
  () => store.getters['automationWorkflowNode/getDraggingNodeId']
)

// Hide context on pan
const { onMove } = useVueFlow()
onMove(() => {
  context.value.hide()
})

const handleDragEnter = () => {
  if (draggingNodeId.value && !props.disabledDrop) {
    isDragOver.value = true
  }
}
const handleDragLeave = () => {
  isDragOver.value = false
}
const handleDrop = () => {
  if (props.disabledDrop) {
    return
  }
  isDragOver.value = false
  emit('toggle-pan', true)
  emit('move-node')
}
const toggleCreateContext = (nodeId) => {
  context.value.show(btn.value.$el, 'bottom', 'left', 10, -225)
}
</script>
