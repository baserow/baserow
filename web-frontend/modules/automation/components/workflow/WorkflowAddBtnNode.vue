<template>
  <div>
    <ButtonFloating
      ref="btn"
      class="workflow-node__add-button"
      :class="{
        'workflow-node__add-button--hover': isDragOver,
        'workflow-node__add-button--active':
          draggingNodeId && !isDropZoneDisabled,
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
import { ref } from '@nuxtjs/composition-api'
import { useVueFlow } from '@vue2-flow/core'

const props = defineProps({
  disabled: {
    type: Boolean,
    default: false,
  },
  btnClass: {
    type: Object,
    required: false,
    default: () => {},
  },
  isDragOver: {
    type: Boolean,
    default: false,
  },
  isDropZoneDisabled: {
    type: Boolean,
    default: false,
  },
  draggingNodeId: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['add-node'])
const context = ref()
const btn = ref()

// Hide context on pan
const { onMove } = useVueFlow()
onMove(() => {
  context.value.hide()
})

const toggleCreateContext = (nodeId) => {
  context.value.show(btn.value.$el, 'bottom', 'left', 10, -225)
}
</script>
