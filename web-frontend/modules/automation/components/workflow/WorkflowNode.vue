<template>
  <div class="workflow-editor__node" @click="emit('clickNode', props.id)">
    <span>ID: {{ id }} </span>

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
            class="context__menu-item-link context__menu-item-link--delete"
            @click="emit('removeNode', props.id)"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            Delete node
          </a>
        </li>
      </ul>
    </Context>
  </div>
</template>

<script setup>
import { ref } from 'vue'

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

const emit = defineEmits(['clickNode', 'removeNode'])

const contextMenu = ref(null)
const editNodeContextToggle = ref(null)
const openContext = () => {
  if (contextMenu.value && editNodeContextToggle.value)
    contextMenu.value.toggle(editNodeContextToggle.value, 'bottom', 'right', 0)
}
</script>
