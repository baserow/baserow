<template>
  <div class="control__elements">
    <PaginatedDropdown
      :fetch-page="fetchPage"
      :value="dropdownValue"
      :add-empty-item="false"
      :initial-display-name="initialDisplayName"
      :error="touched && !valid"
      :fetch-on-open="lazyLoad"
      :disabled="readOnly"
      :include-display-name-in-selected-event="true"
      :value-name="rowDisplayName"
      @input="updateValue($event)"
      @hide="touch()"
    ></PaginatedDropdown>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
  </div>
</template>

<script>
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import formViewLinkRowField from '@baserow/modules/database/mixins/formViewLinkRowField'

export default {
  name: 'FormViewFieldLinkRow',
  components: { PaginatedDropdown },
  mixins: [rowEditField, formViewLinkRowField],
  emits: ['update'],
  computed: {
    dropdownValue() {
      return this.value.length === 0 ? false : this.value[0].id
    },
    initialDisplayName() {
      return this.value.length === 0 ? '' : this.rowDisplayName(this.value[0])
    },
  },
  methods: {
    updateValue({ value, displayName, item }) {
      if (value === null || value === '') {
        this.$emit('update', [], this.value)
        return
      }
      const selection = [
        { id: value, value: this.resolveRowValue(item, displayName) },
      ]
      this.$emit('update', selection, this.value)
    },
  },
}
</script>
