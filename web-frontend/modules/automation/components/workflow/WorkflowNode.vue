<template>
  <div class="workflow-editor__node">
    <div class="workflow-editor__node-icon">
      <i class="iconoir-table"></i>
    </div>

    <h1 class="workflow-editor__node-title">
      {{ props.id }} Row is created in Projects very long text
    </h1>

    <Badge rounded color="yellow" size="large">
      {{ $t('workflowNode.actionConfigure') }}</Badge
    >

    <a
      v-if="!props.data.readOnly"
      ref="editNodeContextToggle"
      class="workflow-editor__node-more-icon"
      @click="openContext()"
    >
      <i class="baserow-icon-more-vertical"></i>
    </a>

    <Context ref="contextMenu" overflow-scroll max-height-if-outside-viewport>
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
    default: () => ({ readOnly: false }),
  },
})

const emit = defineEmits(['removeNode', 'duplicateNode'])

const contextMenu = ref(null)
const editNodeContextToggle = ref(null)
const openContext = () => {
  if (contextMenu.value && editNodeContextToggle.value) {
    contextMenu.value.toggle(editNodeContextToggle.value, 'bottom', 'right', 0)
  }
}

// Hide the context menu when user pan the canvas
onMove(() => {
  contextMenu.value.hide()
})
</script>
