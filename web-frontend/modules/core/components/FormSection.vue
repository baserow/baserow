<template>
  <div class="form-section">
    <div class="form-section__title-container">
      <h3 v-if="title" class="form-section__title">{{ title }}</h3>
      <div>
        <slot name="title-slot"></slot>
      </div>
    </div>
    <slot />
  </div>
</template>

<script>
export default {
  name: 'FormSection',
  props: {
    title: {
      type: String,
      required: false,
      default: null,
    },
  },
}
</script>
