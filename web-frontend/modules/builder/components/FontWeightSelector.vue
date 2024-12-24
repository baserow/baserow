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
  },
  computed: {
    fontWeights() {
      return Object.values(this.$registry.getAll('fontWeight')).sort((a, b) =>
        a.weight < b.weight
      )
    },
  },
}
</script>
