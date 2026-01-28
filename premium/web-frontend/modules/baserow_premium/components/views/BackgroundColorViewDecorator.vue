<template>
  <div :class="backgroundClass">
    <slot />
  </div>
</template>

<script>
export default {
  name: 'BackgroundColorViewDecorator',
  props: {
    value: {
      type: String,
      required: true,
    },
  },
  computed: {
    backgroundClass() {
      return this.value ? `background-color--${this.value}` : null
    },
  },
}
</script>
