<template>
  <div
    :class="{
      'workflow-add-button-container': true,
      'workflow-add-button-container--drop-zone': props.data.isDropZone,
      'workflow-add-button-container--active-drop-zone':
        props.data.isActiveDropZone,
    }"
    :data-id="props.id"
  >
    <ButtonFloating
      class="workflow-add-button-floating"
      :icon="iconClass"
      size="small"
      :disabled="props.data.disabled"
      :title="displayTitle"
      @click="handleClick"
      @pointerdown="handlePointerDown"
      @pointerup="handlePointerUp"
    ></ButtonFloating>
    <div
      v-if="props.data.isDropZone"
      class="workflow-add-button-drop-zone"
      :class="{
        'workflow-add-button-drop-zone--active': props.data.isActiveDropZone,
      }"
    >
      <div
        v-if="props.data.isActiveDropZone"
        class="workflow-add-button-placeholder"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { computed, useContext } from '@nuxtjs/composition-api'
const { app } = useContext()

const props = defineProps({
  id: {
    type: String,
    default: null,
  },
  position: {
    type: Object,
    default: () => ({ x: 0, y: 0 }),
  },
  data: {
    type: Object,
    default: () => ({ nodeId: null }),
  },
})

const emit = defineEmits(['addNode', 'mousedown', 'mouseup'])

const iconClass = computed(() => {
  return props.data.isActiveDropZone ? 'iconoir-check' : 'iconoir-plus'
})

/**
 * Computed property to determine the display title of the button.
 * If `data.debug` is true, it shows a debug message with the node ID and
 * output UID (if available). Otherwise, it shows a standard title.
 * @type {string} - The title to display on the button.
 */
const displayTitle = computed(() => {
  return props.data.debug
    ? app.i18n.t('workflowAddNode.displayTitleDebug', {
        id: props.id,
        outputUid: props.data.outputUid || 'none',
      })
    : app.i18n.t('workflowAddNode.displayTitle')
})

const handleClick = () => {
  if (!props.data.disabled) {
    emit('addNode', props.data.nodeId)
  }
}

const handlePointerDown = (event) => {
  emit('mousedown', event)
}

const handlePointerUp = (event) => {
  emit('mouseup', event)
}
</script>
