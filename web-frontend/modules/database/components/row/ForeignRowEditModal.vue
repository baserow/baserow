<template>
  <RowEditModal
    ref="modal"
    :read-only="readOnly"
    :database="database"
    :table="table"
    :rows="[]"
    :all-fields-in-table="fields"
    :visible-fields="fields"
    :fields-sortable="fieldsSortable"
    :can-modify-fields="canModifyFields"
    @hidden="$emit('hidden', $event)"
    @update="update"
  ></RowEditModal>
</template>

<script>
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal'
import FieldService from '@baserow/modules/database/services/field'
import RowService from '@baserow/modules/database/services/row'
import { populateField } from '@baserow/modules/database/store/field'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  extractRowReadOnlyValues,
  prepareNewOldAndUpdateRequestValues,
} from '@baserow/modules/database/utils/row'

/**
 * This component can open the row edit modal having the fields of that table in the
 * fields store. It will make a request to the backend fetching the missing
 * information.
 */
export default {
  name: 'ForeignRowEditModal',
  components: { RowEditModal },
  props: {
    tableId: {
      type: Number,
      required: true,
    },
    fieldsSortable: {
      type: Boolean,
      required: false,
      default: () => true,
    },
    canModifyFields: {
      type: Boolean,
      required: false,
      default: () => true,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['hidden', 'refresh-row'],
  data() {
    return {
      fetchedTableAndFields: false,
      table: {},
      fields: [],
    }
  },
  computed: {
    database() {
      const databaseType = DatabaseApplicationType.getType()
      for (const application of this.$store.getters['application/getAll']) {
        if (application.type !== databaseType) {
          continue
        }

        const foundTable = application.tables.find(
          ({ id }) => id === this.tableId
        )

        if (foundTable) {
          return application
        }
      }

      return undefined
    },
  },
  methods: {
    async fetchTableAndFields() {
      // Find the table in the applications to prevent a request to the backend and to
      // maintain reactivity with the real time updates.
      const databaseType = DatabaseApplicationType.getType()
      for (const application of this.$store.getters['application/getAll']) {
        if (application.type !== databaseType) {
          continue
        }

        const foundTable = application.tables.find(
          ({ id }) => id === this.tableId
        )

        if (foundTable) {
          this.table = foundTable
          break
        }
      }

      // Because we don't have the fields in the store we need to fetch those for this
      // table.
      const { data: fieldData } = await FieldService(this.$client).fetchAll(
        this.tableId
      )
      const { $registry } = useNuxtApp()
      fieldData.forEach((part, index) => {
        populateField(fieldData[index], $registry)
      })
      this.fields = fieldData

      // Mark the table and fields as fetched, so that we don't have to do that a
      // second time when the user opens another row.
      this.fetchedTableAndFields = true
    },

    async show(rowId) {
      if (!this.fetchedTableAndFields) {
        await this.fetchTableAndFields()
      }

      const { data: rowData } = await RowService(this.$client).get(
        this.tableId,
        rowId
      )
      this.$refs.modal.show(rowData.id, rowData)
    },
    /**
     * A method which listens for `update` event emitted by other components
     * (f. ex. RowEditModalFieldsList). It updates the foreign row that's being
     * edited in a real-time manner.
     */
    async update({ field, row, value, oldValue, table }) {
      const { newRowValues, oldRowValues, updateRequestValues } =
        prepareNewOldAndUpdateRequestValues(
          row,
          this.fields,
          field,
          value,
          oldValue,
          this.$registry
        )

      this.$store.dispatch('rowModal/updated', {
        tableId: this.tableId,
        values: newRowValues,
      })

      // Attempt to call the `rowModal/updated` action in the store which is
      // usually called when we receive a real time row update event, this updates
      // the foreign row that's being edited in a real-time manner:
      try {
        const { data } = await RowService(this.$client).update(
          table.id,
          row.id,
          updateRequestValues
        )
        const readOnlyData = extractRowReadOnlyValues(
          data,
          this.fields,
          this.$registry
        )
        this.$store.dispatch('rowModal/updated', {
          tableId: this.tableId,
          values: readOnlyData,
        })
        this.$emit('refresh-row')
        // In case the above fails, previous row values should be restored:
      } catch (error) {
        this.$store.dispatch('rowModal/updated', {
          tableId: this.tableId,
          values: oldRowValues,
        })
        notifyIf(error, 'row')
      }
    },
  },
}
</script>
