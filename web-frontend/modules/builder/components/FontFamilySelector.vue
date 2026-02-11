<template>
  <Dropdown :value="currentValue" fixed-items @input="input">
    <DropdownItem
      v-for="fontFamily in fontFamilies"
      :key="fontFamily.getType()"
      :value="fontFamily.getType()"
      :name="fontFamily.name"
    />
  </Dropdown>
</template>

<script>
export default {
  name: 'FontFamilySelector',
  props: {
    /**
     * The model value of the dropdown in Vue 3 style.
     */
    modelValue: {
      type: String,
      default: undefined,
    },
    /**
     * The model value of the dropdown in Vue 2 style.
     */
    value: {
      type: String,
      required: false,
      default: 'Inter',
    },
  },
  emits: ['input', 'update:modelValue'],
  computed: {
    // This computed must be used instead of .value
    currentValue() {
      return this.modelValue !== undefined ? this.modelValue : this.value
    },
    fontFamilies() {
      return Object.values(this.$registry.getAll('fontFamily')).sort((a, b) =>
        a.name.localeCompare(b.name)
      )
    },
  },
  methods: {
    input(value) {
      // emitting the updated value Vue 3 style.
      this.$emit('update:modelValue', value)
      // emitting the updated value Vue 2 style.
      this.$emit('input', value)
    },
  },
}
</script>
