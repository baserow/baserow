<template>
  <div
    :key="elementType.name"
    v-tooltip="disabled ? disabledMessage : elementType.description"
    class="add-element-card"
    :class="{ 'add-element-card--disabled': disabled }"
    v-on="$listeners"
  >
    <div v-if="loading" class="loading"></div>
    <div v-else class="add-element-card__element-type">
      <div
        class="add-element-card__element-type-icon"
        :class="`add-element-card__element-type-icon-${elementType.getType()}`"
      ></div>
    </div>
    <span class="add-element-card__label">{{ elementType.name }}</span>
  </div>
</template>

<script>
export default {
  name: 'AddElementCard',
  props: {
    elementType: {
      type: Object,
      required: true,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    disabledMessage: {
      type: String,
      required: false,
      default: '',
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
}
</script>
