import { getPrimaryOrFirstField } from '@baserow/modules/database/utils/field'
import BigNumber from 'bignumber.js'

export default {
  data() {
    return {
      // If true, then the user must choose which values will be deleted. This only
      // happens if field.link_row_multiple_relationships == false, meaning that only
      // one relationship can persist.
      removingRelationships: false,
      removingRelationShipIds: [],
    }
  },
  computed: {
    /**
     * Returns the value of the field that can be used when creating a new row
     * in the linked table starting from the current row.
     */
    presetsForNewRowInLinkedTable() {
      const presets = {}
      const value = this.primaryFieldLinkRowValue
      if (value && Boolean(value.id)) {
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
    visibleValues() {
      if (this.removingRelationships) {
        return this.value.filter(
          (v) => !this.removingRelationShipIds.includes(v.id)
        )
      } else {
        return this.value
      }
    },
    canAddValue() {
      return (
        this.field.link_row_multiple_relationships ||
        (Array.isArray(this.value) && this.value.length < 1)
      )
    },
  },
  methods: {
    /**
     * Removes an existing relation from the value.
     */
    removeValue(event, value, id) {
      // If the cell is in delete relationships mode, then the newly deleted
      // relationship must be added to the list of to be deleted items.
      if (this.removingRelationships) {
        this.removingRelationShipIds.push(id)
        // The backend only accepts one value in that case, so if one is left, then
        // the value is actually updated.
        if (this.removingRelationShipIds.length + 1 === value.length) {
          const newValue = JSON.parse(JSON.stringify(value)).filter(
            (v) => !this.removingRelationShipIds.includes(v.id)
          )
          this.removingRelationships = false
          this.removingRelationShipIds = []
          this.$emit('update', newValue, value)
        }
        return
      }

      // If it's not allowed to have multiple relationships, then the backend will
      // accept only one value during update. Because it will otherwise fail, the cell
      // is put in a mode where the user must delete all relationships except one.
      if (!this.field.link_row_multiple_relationships && value.length > 2) {
        this.removingRelationships = true
        this.removingRelationShipIds = [id]
        return
      }

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

      const newValue = JSON.parse(JSON.stringify(value))
      newValue.push({ id: row.id, value: rowValue, order: row.order })
      // Match the backend order sorting
      newValue.sort((a, b) => {
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
