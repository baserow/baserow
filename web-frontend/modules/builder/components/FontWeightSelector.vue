<template>
  <Dropdown
    :value="fontWeightValue"
    fixed-items
    @input="$emit('input', $event)"
  >
    <DropdownItem
      v-for="fontWeight in fontWeights"
      :key="fontWeight.getType()"
      :value="fontWeight.getType()"
      :name="fontWeight.name"
    />
  </Dropdown>
</template>

<script>
export default {
  name: 'FontWeightSelector',
  props: {
    value: {
      type: String,
      required: false,
      default: 'Regular',
    },
    font: {
      type: String,
      required: false,
      default: null,
    },
  },
  computed: {
    supportedWeights() {
      return this.font ? this.fontFamilyType.weights : ['regular']
    },
    fontFamilyType() {
      return this.$registry.get('fontFamily', this.font)
    },
    fontWeights() {
      return Object.values(this.$registry.getAll('fontWeight'))
        .filter((fontWeight) => this.supportedWeights.includes(fontWeight.type))
        .sort((a, b) => a.weight - b.weight)
    },
    fontWeightValue: {
      get() {
        return this.value
      },
      set(newValue) {
        this.$emit('input', newValue)
      },
    },
  },

  watch: {
    /**
     * Check if the updated font supports the currently selected weight. If not,
     * set the font weight to 'regular', which should be supported by all fonts.
     */
    font() {
      if (!this.supportedWeights.includes(this.value)) {
        this.fontWeightValue = this.fontFamilyType.defaultWeight
      }
    },
  },
}
</script>
