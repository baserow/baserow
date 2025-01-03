<template>
  <FieldSelectOptionsDropdown
    :value="copy"
    :options="field.select_options"
    :disabled="disabled"
    :fixed-items="true"
    class="dropdown--floating filters__value-dropdown"
    @input="input"
  ></FieldSelectOptionsDropdown>
</template>

<script>
import FieldSelectOptionsDropdown from '@baserow/modules/database/components/field/FieldSelectOptionsDropdown'
import viewFilter from '@baserow/modules/database/mixins/viewFilter'

export default {
  name: 'ViewFilterTypeSelectOptions',
  components: { FieldSelectOptionsDropdown },
  mixins: [viewFilter],
  computed: {
    copy() {
      const value = String(this.filter.value ?? '')
      return value === '' || value.includes(',')
        ? null
        : parseInt(value) || null
    },
  },
  methods: {
    input(value) {
      value = value === null ? '' : value.toString()
      this.$emit('input', value)
    },
  },
}
</script>
