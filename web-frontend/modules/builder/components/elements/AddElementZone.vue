<template>
  <div
    class="add-element-zone"
    :class="{
      'add-element-zone--disabled': disabled,
      'add-element-zone--drag-active': isValidDropTarget,
      'add-element-zone--drag-over': isDragOver,
    }"
    @click="!disabled && $emit('add-element')"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div v-tooltip="disabled ? tooltip : null" class="add-element-zone__button">
      <i class="iconoir-plus add-element-zone__icon"></i>
      <span v-if="label" class="add-element-zone__label">{{ label }}</span>
    </div>
  </div>
</template>

<script>
import { useDropElementTarget } from '@baserow/modules/builder/composables/useDropElementTarget'

export default {
  name: 'AddElementZone',
  props: {
    parentElement: {
      type: Object,
      required: false,
      default: null,
    },
    // Explicit target page when parentElement is null (e.g. empty page drop zone).
    page: {
      type: Object,
      required: false,
      default: null,
    },
    placeInContainer: {
      type: [String, null],
      required: false,
      default: null,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    tooltip: {
      type: String,
      required: false,
      default: null,
    },
    label: {
      type: String,
      required: false,
      default: null,
    },
  },
  emits: ['add-element', 'dragover', 'dragleave', 'drop'],
  setup(props) {
    return useDropElementTarget({
      parentElement: props.parentElement,
      placeInContainer: props.placeInContainer,
      page: props.page,
    })
  },
}
</script>
