<template>
  <FieldSelectOptionsDropdown
    :value="copy"
    :options="field.select_options"
    :disabled="disabled"
    :fixed-items="true"
    :multiple="true"
    :show-empty-value="false"
    class="dropdown--floating filters__value-dropdown"
    @input="input"
  ></FieldSelectOptionsDropdown>
</template>

<script>
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown'
import viewFilter from '@baserow/modules/database/mixins/viewFilter'

export default {
  name: 'ViewFilterTypeMultipleSelectOptions',
  components: { FieldSelectOptionsDropdown },
  mixins: [viewFilter],
  computed: {
    copy() {
      const value = String(this.filter.value ?? '')
      return value
        .split(',')
        .map((value) => parseInt(value))
        .filter((value) => !isNaN(value))
    },
  },
  methods: {
    input(value) {
      value = value.join(',')
      this.$emit('input', value)
    },
  },
}
</script>
