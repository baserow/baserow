import { getPrimaryOrFirstField } from '@baserow/modules/database/utils/field'
import BigNumber from 'bignumber.js'

export default {
  computed: {
    /**
     * Returns the value of the field that can be used when creating a new row
     * in the linked table starting from the current row.
     */
    presetsForNewRowInLinkedTable() {
      const presets = {}
      const value = this.primaryFieldLinkRowValue
      if (value) {
        presets[`field_${this.field.link_row_related_field_id}`] = [value]
      }
      return presets
    },
    /**
     * Returns the value of the field.
     */
    primaryFieldLinkRowValue() {
      // Set the starting row as preset so that can be used later if the user wants to create a new row
      // starting from the selected row.
      if (!this.allFieldsInTable) {
        return
      }
      const primaryField = getPrimaryOrFirstField(this.allFieldsInTable)
      const primaryFieldType = this.$registry.get(
        'field',
        primaryField._.type.type
      )
      return {
        id: this.row.id,
        value: primaryFieldType.toHumanReadableString(
          primaryField,
          this.row[`field_${primaryField.id}`]
        ),
      }
    },
  },
  methods: {
    /**
     * Removes an existing relation from the value.
     */
    removeValue(event, value, id) {
      const newValue = JSON.parse(JSON.stringify(value))
      const index = newValue.findIndex((item) => item.id === id)
      if (index === -1) {
        return
      }

      newValue.splice(index, 1)
      this.$emit('update', newValue, value)
    },
    /**
     * Adds a new relation to the value. This typically happens via the modal.
     */
    addValue(value, { row, primary }) {
      // Check if the relation already exists.
      for (let i = 0; i < value.length; i++) {
        if (value[i].id === row.id) {
          return
        }
      }

      // Prepare the new value with all the relations and emit that value to the
      // parent.
      const rowValue = this.$registry
        .get('field', primary.type)
        .toHumanReadableString(primary, row[`field_${primary.id}`])
      // The backend sort by order first and then by id, but we don't have the order
      // here, so we just sort by id
      const valueCopy = JSON.parse(JSON.stringify(value))
      const newValue = [
        ...valueCopy,
        { id: row.id, value: rowValue, order: row.order },
      ].toSorted((a, b) => {
        const orderA = new BigNumber(a.order)
        const orderB = new BigNumber(b.order)
        return orderA.isLessThan(orderB)
          ? -1
          : orderA.isEqualTo(orderB)
          ? a.id - b.id
          : 1
      })
      this.$emit('update', newValue, value)
    },
  },
}
