<template>
  <div class="left-border-decorator" :class="borderClass"></div>
</template>

<script>
export default {
  name: 'LeftBorderColorViewDecorator',
  props: {
    value: {
      type: String,
      required: true,
    },
  },
  computed: {
    borderClass() {
      return this.value ? `background-color--${this.value}` : null
    },
  },
}
</script>
