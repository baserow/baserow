<template>
  <div
    class="add-element-zone"
    :class="{
      'add-element-zone--disabled': disabled,
      'add-element-zone--drag-active': isValidDropTarget,
      'add-element-zone--drag-over': isDragOver,
    }"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div
      v-tooltip="disabled ? tooltip : null"
      class="add-element-zone__button"
      @click="!disabled && $emit('add-element')"
    >
      <i class="iconoir-plus add-element-zone__icon"></i>
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
      required: true,
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
  },
  emits: ['add-element', 'dragover', 'dragleave', 'drop'],
  setup(props) {
    return useDropElementTarget({
      parentElement: props.parentElement,
      placeInContainer: props.placeInContainer,
    })
  },
}
</script>
