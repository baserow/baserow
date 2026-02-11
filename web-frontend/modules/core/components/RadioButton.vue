<template>
  <Button
    type="secondary"
    v-bind="restProps"
    :loading="loading"
    :disabled="disabled"
    :icon="icon"
    :title="title"
    :active="selected"
    @click.prevent="select(value)"
  >
    <slot></slot>
  </Button>
</template>

<script>
export default {
  name: 'RadioButton',
  props: {
    value: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: '',
    },
    modelValue: {
      type: [String, Number, Boolean, Object],
      required: false,
      default: '',
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
  emits: ['input', 'update:modelValue'],
  computed: {
    selected() {
      return this.modelValue === this.value
    },
    restProps() {
      const { value, modelValue, ...rest } = this.$attrs
      if (this.selected) {
        rest.active = true
      }
      return rest
    },
  },
  methods: {
    select(value) {
      if (this.disabled || this.selected) {
        return
      }
      this.$emit('update:modelValue', value)
      this.$emit('input', value)
    },
  },
}
</script>
