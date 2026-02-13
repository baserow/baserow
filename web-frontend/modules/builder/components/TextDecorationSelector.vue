<template>
  <div class="text-decoration-selector">
    <SwitchButton
      :value="currentValue[0]"
      icon="iconoir-underline"
      :title="$t('textDecorationSelector.underline')"
      @input="toggle(0)"
    />
    <SwitchButton
      :value="currentValue[1]"
      icon="iconoir-strikethrough"
      :title="$t('textDecorationSelector.stroke')"
      @input="toggle(1)"
    />
    <SwitchButton
      :value="currentValue[2]"
      icon="iconoir-text"
      :title="$t('textDecorationSelector.uppercase')"
      @input="toggle(2)"
    />
    <SwitchButton
      :value="currentValue[3]"
      icon="iconoir-italic"
      :title="$t('textDecorationSelector.italic')"
      @input="toggle(3)"
    />
  </div>
</template>

<script>
export default {
  name: 'TextDecorationSelector',
  props: {
    /**
     * Vue 3 model binding.
     */
    modelValue: {
      type: Array,
      default: undefined,
    },

    /**
     * Vue 2 model binding.
     */
    value: {
      type: Array,
      required: false,
      default: () => [false, false, false, false],
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    // Prefer Vue 3 modelValue if provided.
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
  },
  methods: {
    toggle(index) {
      const updated = this.currentValue.map((v, i) => (i === index ? !v : v))

      // Vue 3 emit
      this.$emit('update:modelValue', updated)
      // Vue 2 emit
      this.$emit('input', updated)
    },
  },
}
</script>
