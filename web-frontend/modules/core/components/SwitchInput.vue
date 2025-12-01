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
     * The value of the switch.
     */
    value: {
      type: [Boolean, Number],
      required: false,
      default: false,
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
  computed: {
    hasSlot() {
      return !!this.$slots.default
    },
    classNames() {
      return {
        'switch--small': this.small,
        'switch--disabled': this.disabled,
        'switch--active': this.value,
        'switch--indeterminate': this.value !== true && this.value !== false,
        [`switch--color-${this.color}`]: true,
      }
    },
  },
  methods: {
    click($event) {
      this.toggle(this.value)
      this.$emit('click', $event)
    },
    toggle(value) {
      if (this.disabled) {
        return
      }
      this.$emit('input', !value)
    },
  },
}
</script>
