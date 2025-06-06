<template>
  <div
    class="workflow-editor__node"
    :data-before-label="
      props.data.isTrigger
        ? $t('workflowNode.beforeLabelTrigger')
        : $t('workflowNode.beforeLabelAction')
    "
  >
    <div class="workflow-editor__node-icon">
      <i class="iconoir-table"></i>
    </div>

    <h1 class="workflow-editor__node-title">{{ props.label }}</h1>

    <Badge v-if="props.data.isInError" rounded color="yellow" size="large">
      {{ $t('workflowNode.actionConfigure') }}</Badge
    >

    <a
      v-if="!props.data.readOnly"
      ref="editNodeContextToggle"
      role="button"
      title="Node options"
      class="workflow-editor__node-more-icon"
      @click="openContext()"
    >
      <i class="baserow-icon-more-vertical"></i>
    </a>

    <Context ref="contextMenu" overflow-scroll max-height-if-outside-viewport>
      <div class="context__menu-title">{{ label }} ({{ props.id }})</div>
      <ul class="context__menu">
        <li class="context__menu-item">
          <a
            class="context__menu-item-link"
            @click="emit('duplicateNode', props.id)"
          >
            <i class="context__menu-item-icon iconoir-copy"></i>
            {{ $t('workflowNode.actionDuplicate') }}
          </a>
          <a
            role="button"
            title="Delete action"
            class="context__menu-item-link context__menu-item-link--delete"
            @click="emit('removeNode', props.id)"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('workflowNode.actionDelete') }}
          </a>
        </li>
      </ul>
    </Context>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useVueFlow } from '@vue2-flow/core'

const { onMove } = useVueFlow()
const props = defineProps({
  id: {
    type: String,
    default: null,
  },
  label: {
    type: String,
    default: null,
  },
  selected: {
    type: Boolean,
    default: false,
  },
  dragging: {
    type: Boolean,
    default: false,
  },
  data: {
    type: Object,
    default: () => ({ readOnly: false, isInError: false }),
  },
})

const emit = defineEmits(['removeNode', 'duplicateNode'])

const contextMenu = ref(null)
const editNodeContextToggle = ref(null)
const openContext = () => {
  if (contextMenu.value && editNodeContextToggle.value) {
    contextMenu.value.toggle(editNodeContextToggle.value, 'bottom', 'left', 0)
  }
}

// Hide the context menu when user pan the canvas
onMove(() => {
  contextMenu.value.hide()
})
</script>
