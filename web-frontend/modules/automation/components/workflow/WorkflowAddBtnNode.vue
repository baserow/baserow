<template>
  <ButtonFloating
    icon="iconoir-plus"
    size="small"
    :disabled="props.data.disabled"
    :title="displayTitle"
    @click="handleClick"
  ></ButtonFloating>
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

const emit = defineEmits(['addNode'])

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
</script>
