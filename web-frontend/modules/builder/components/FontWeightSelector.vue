<template>
  <Dropdown :value="value" fixed-items @input="$emit('input', $event)">
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
      return this.font
        ? this.$registry.get('fontFamily', this.font).weights
        : ['regular']
    },

    fontWeights() {
      return Object.values(this.$registry.getAll('fontWeight'))
        .filter((fontWeight) => this.supportedWeights.includes(fontWeight.type))
        .sort((a, b) => a.weight - b.weight)
    },
  },
}
</script>
