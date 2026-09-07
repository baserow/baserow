// Host components provide the `groupByField`, `groupPath` and `groupDisplay` computeds.
export default {
  computed: {
    fieldType() {
      if (!this.groupByField) {
        return null
      }
      return this.$registry.get('field', this.groupByField.type)
    },
    groupValue() {
      const field = this.groupByField
      if (!field) {
        return null
      }
      return this.groupPath[`field_${field.id}`]
    },
    displayValue() {
      const field = this.groupByField
      const display = this.groupDisplay
      if (!field || !display) {
        return undefined
      }
      const key = `field_${field.id}`
      return key in display ? display[key] : undefined
    },
    rowValueForGroup() {
      const field = this.groupByField
      if (!field || !this.fieldType) {
        return null
      }
      // Reference fields (selects, links, collaborators) only render from `display`.
      if (this.displayValue !== undefined) {
        return this.displayValue
      }
      return this.fieldType.getRowValueFromGroupValue(field, this.groupValue)
    },
    isEmptyValue() {
      const value = this.rowValueForGroup
      if (Array.isArray(value)) {
        return value.length === 0
      }
      return value === null || value === undefined || value === ''
    },
    groupByComponent() {
      if (this.isEmptyValue || !this.groupByField || !this.fieldType) {
        return null
      }
      if (typeof this.fieldType.getGroupByComponent !== 'function') {
        return null
      }
      return this.fieldType.getGroupByComponent(this.groupByField)
    },
    fallbackValueText() {
      const value = this.rowValueForGroup
      if (value === null || value === undefined) {
        return ''
      }
      if (typeof value === 'boolean') {
        return value ? 'true' : 'false'
      }
      if (this.fieldType?.toHumanReadableString) {
        try {
          const text = this.fieldType.toHumanReadableString(
            this.groupByField,
            value
          )
          if (typeof text === 'string') {
            return text
          }
        } catch (_) {
          // Fall back to the generic object/string rendering below.
        }
      }
      if (typeof value === 'object') {
        if ('value' in value) {
          return value.value
        }
        return JSON.stringify(value)
      }
      return String(value)
    },
  },
}
