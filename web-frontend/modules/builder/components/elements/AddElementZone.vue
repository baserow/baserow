<template>
  <div
    class="add-element-zone"
    :class="{ 'add-element-zone--disabled': disabled }"
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
  },
}
</script>
