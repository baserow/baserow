<template>
  <Dropdown :value="value" fixed-items @input="$emit('input', $event)">
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
    value: {
      type: String,
      required: false,
      default: 'Inter',
    },
  },
  computed: {
    fontFamilies() {
      return Object.values(this.$registry.getAll('fontFamily')).sort((a, b) =>
        a.name.localeCompare(b.name)
      )
    },
  },
}
</script>
