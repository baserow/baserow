<template>
  <div class="switch" :class="classNames" @click="click">
    <div v-if="hasSlot" class="switch__label"><slot></slot></div>
  </div>
</template>

<script>
export default {
  name: 'SwitchInput',
  props: {
    /**
     * The model value of the textarea in Vue 3 style.
     */
    modelValue: {
      type: [Boolean, Number],
      required: false,
      default: undefined,
    },
    /**
     * The value of the switch.
     */
    value: {
      type: [Boolean, Number],
      required: false,
      default: undefined,
    },
    /**
     * The size of the switch.
     */
    small: {
      type: Boolean,
      required: false,
      default: false,
    },
    /**
     * Whether the switch is disabled.
     */
    disabled: {
      type: Boolean,
      required: false,
      default: false,
    },
    color: {
      type: String,
      required: false,
      validator: function (value) {
        return ['green', 'neutral'].includes(value)
      },
      default: 'green',
    },
  },
  emits: ['input', 'update:modelValue', 'click'],
  computed: {
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
    hasSlot() {
      const slot = this.$slots.default
      return !!(slot && slot().length)
    },
    classNames() {
      return {
        'switch--small': this.small,
        'switch--disabled': this.disabled,
        'switch--active': this.currentValue,
        'switch--indeterminate':
          this.currentValue !== true && this.currentValue !== false,
        [`switch--color-${this.color}`]: true,
      }
    },
  },
  methods: {
    click($event) {
      this.toggle(this.currentValue)
      this.$emit('click', $event)
    },
    toggle(value) {
      if (this.disabled) {
        return
      }
      // emitting the updated value Vue 3 style.
      this.$emit('update:modelValue', !value)
      // emitting the updated value Vue 2 style.
      this.$emit('input', !value)
    },
  },
}
</script>
