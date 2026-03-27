<template>
  <div
    class="add-element-zone"
    :class="{
      'add-element-zone--disabled': disabled,
      'add-element-zone--drag-active': isDragActive,
      'add-element-zone--drag-over': isDragOver,
    }"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div
      v-if="!isDragActive"
      v-tooltip="disabled ? tooltip : null"
      class="add-element-zone__button"
      @click="!disabled && $emit('add-element')"
    >
      <i class="iconoir-plus add-element-zone__icon"></i>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AddElementZone',
  props: {
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
    isDragActive: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['add-element', 'dragover', 'dragleave', 'drop'],
  data() {
    return {
      isDragOver: false,
    }
  },
  methods: {
    onDragOver(event) {
      if (!this.isDragActive) return
      event.preventDefault()
      event.stopPropagation()
      this.isDragOver = true
      this.$emit('dragover', event)
    },
    onDragLeave(event) {
      if (!this.isDragActive) return
      this.isDragOver = false
      this.$emit('dragleave', event)
    },
    onDrop(event) {
      if (!this.isDragActive) return
      event.preventDefault()
      event.stopPropagation()
      this.isDragOver = false
      this.$emit('drop', event)
    },
  },
}
</script>
