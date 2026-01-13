<template>
  <ButtonIcon
    type="secondary"
    v-bind="restProps"
    :loading="loading"
    :disabled="disabled"
    :icon="icon"
    :title="title"
    :active="value"
    @click.prevent="select()"
  >
    <slot></slot>
  </ButtonIcon>
</template>

<script>
export default {
  name: 'SwitchButton',
  props: {
    value: {
      type: Boolean,
      required: false,
      default: false,
    },
    loading: {
      type: Boolean,
      required: false,
      default: false,
    },
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    icon: {
      type: String,
      required: false,
      default: '',
    },
    title: {
      type: String,
      required: false,
      default: '',
    },
  },
  emits: ['input'],
  computed: {
    restProps() {
      const { value, modelValue, ...rest } = this.$attrs
      return rest
    },
  },
  methods: {
    select() {
      if (this.disabled) {
        return
      }
      this.$emit('input', !this.value)
    },
  },
}
</script>
