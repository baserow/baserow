<template>
  <div class="calendar-view">
    <CalendarMonth
      :fields="fields"
      :store-prefix="storePrefix"
      :loading="loading"
      :read-only="readOnly"
      :database="database"
      :table="table"
      :view="view"
      @edit-row="openRowEditModal($event)"
      @create-row="openCreateRowModal"
      @row-context="showRowContext($event.event, $event.row)"
    ></CalendarMonth>
    <RowCreateModal
      ref="rowCreateModal"
      :database="database"
      :table="table"
      :view="view"
      :primary-is-sortable="true"
      :visible-fields="visibleCardFields"
      :hidden-fields="hiddenFields"
      :show-hidden-fields="showHiddenFieldsInRowModal"
      :all-fields-in-table="fields"
      @toggle-hidden-fields-visibility="
        showHiddenFieldsInRowModal = !showHiddenFieldsInRowModal
      "
      @created="createRow"
      @order-fields="orderFields"
      @toggle-field-visibility="toggleFieldVisibility"
      @field-updated="$emit('refresh', $event)"
      @field-deleted="$emit('refresh')"
    ></RowCreateModal>
    <RowEditModal
      ref="rowEditModal"
      enable-navigation
      :database="database"
      :table="table"
      :view="view"
      :all-fields-in-table="fields"
      :primary-is-sortable="false"
      :visible-fields="visibleCardFields"
      :hidden-fields="hiddenFields"
      :rows="allRows"
      :read-only="
        readOnly ||
        (!$hasPermission(
          'database.table.update_row',
          table,
          database.workspace.id
        ) &&
          !$hasPermission(
            'database.table.view.update_row',
            view,
            database.workspace.id
          ))
      "
      :show-hidden-fields="showHiddenFieldsInRowModal"
      @refresh-row="refreshRow"
      @hidden="$emit('selected-row', undefined)"
      @toggle-hidden-fields-visibility="
        showHiddenFieldsInRowModal = !showHiddenFieldsInRowModal
      "
      @update="updateValue"
      @order-fields="orderFields"
      @toggle-field-visibility="toggleFieldVisibility"
      @field-updated="$emit('refresh', $event)"
      @field-deleted="$emit('refresh')"
      @field-created="
        fieldCreated($event)
        showHiddenFieldsInRowModal = true
      "
      @field-created-callback-done="afterFieldCreatedUpdateFieldOptions"
      @navigate-previous="$emit('navigate-previous', $event)"
      @navigate-next="$emit('navigate-next', $event)"
    ></RowEditModal>
    <Context
      ref="cardContext"
      :overflow-scroll="true"
      :hide-on-scroll="true"
      :hide-on-resize="true"
      :max-height-if-outside-viewport="true"
      class="context__menu-wrapper"
    >
      <ul class="context__menu">
        <li
          v-if="
            !readOnly &&
            ($hasPermission(
              'database.table.delete_row',
              table,
              database.workspace.id
            ) ||
              $hasPermission(
                'database.table.view.delete_row',
                view,
                database.workspace.id
              ))
          "
          class="context__menu-item"
        >
          <a
            class="context__menu-item-link js-ctx-delete-row"
            @click="deleteRow(selectedRow)"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('gridView.deleteRow') }}
          </a>
        </li>
      </ul>
    </Context>
  </div>
</template>
<script>
import CalendarMonth from '@baserow_premium/components/views/calendar/CalendarMonth'
import {
  filterHiddenFieldsFunction,
  filterVisibleFieldsFunction,
  sortFieldsByOrderAndIdFunction,
} from '@baserow/modules/database/utils/view'
import { mapGetters } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'
import viewHelpers from '@baserow/modules/database/mixins/viewHelpers'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal.vue'
import { populateRow } from '@baserow/modules/database/store/view/grid'
import { clone } from '@baserow/modules/core/utils/object'
import RowCreateModal from '@baserow/modules/database/components/row/RowCreateModal.vue'

export default {
  name: 'CalendarView',
  components: {
    CalendarMonth,
    RowEditModal,
    RowCreateModal,
  },
  mixins: [viewHelpers],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    loading: {
      type: Boolean,
      required: true,
    },
    storePrefix: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      showHiddenFieldsInRowModal: false,
      selectedRow: null,
      refreshingRow: false,
    }
  },
  computed: {
    visibleCardFields() {
      return this.fields
        .filter(filterVisibleFieldsFunction(this.fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(this.fieldOptions))
    },
    hiddenFields() {
      return this.fields
        .filter(filterHiddenFieldsFunction(this.fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(this.fieldOptions))
    },
  },
  watch: {
    row: {
      deep: true,
      handler(row, oldRow) {
        if (this.$refs.rowEditModal) {
          if (
            (oldRow === null && row !== null) ||
            (oldRow && row && oldRow.id !== row.id)
          ) {
            this.populateAndEditRow(row)
          } else if (oldRow !== null && row === null) {
            // Pass emit=false as argument into the hide function because that will
            // prevent emitting another `hidden` event of the `RowEditModal` which can
            // result in the route changing twice.
            this.$refs.rowEditModal.hide(false)
          }
        }
      },
    },
  },
  mounted() {
    if (this.row !== null) {
      this.populateAndEditRow(this.row)
    }
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        row: 'rowModalNavigation/getRow',
        allRows:
          this.$options.propsData.storePrefix + 'view/calendar/getAllRows',
        fieldOptions:
          this.$options.propsData.storePrefix +
          'view/calendar/getAllFieldOptions',
        getDateField:
          this.$options.propsData.storePrefix + 'view/calendar/getDateField',
      }),
    }
  },
  methods: {
    async updateValue({ field, row, value, oldValue }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/calendar/updateRowValue',
          {
            table: this.table,
            view: this.view,
            fields: this.fields,
            row,
            field,
            value,
            oldValue,
          }
        )
      } catch (error) {
        notifyIf(error, 'field')
      }
    },
    /**
     * When the row edit modal is opened we notifiy
     * the Table component that a new row has been selected,
     * such that we can update the path to include the row id.
     */
    openRowEditModal(row) {
      this.$refs.rowEditModal.show(row.id)
      this.$emit('selected-row', row)
    },
    /**
     * Populates a new row and opens the row edit modal
     * to edit the row.
     */
    populateAndEditRow(row) {
      const rowClone = populateRow(clone(row))
      this.$store.dispatch(this.storePrefix + 'view/calendar/selectRow', {
        row: rowClone,
        fields: this.fields,
      })

      this.$refs.rowEditModal.show(row.id, rowClone)
    },
    async createRow({ row, callback }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/calendar/createNewRow',
          {
            view: this.view,
            table: this.table,
            fields: this.fields,
            values: row,
          }
        )
        callback()
      } catch (error) {
        callback(error)
      }
    },

    openCreateRowModal(event) {
      const defaults = {}
      const dateField = this.getDateField(this.fields)
      if (!dateField) {
        // Cannot create a row without a proper date field
        return
      }
      const fieldType = this.$registry.get('field', dateField.type)
      if (
        event?.day?.date != null &&
        fieldType.canWriteFieldValues(dateField)
      ) {
        const name = `field_${dateField.id}`
        if (dateField.date_include_time) {
          defaults[name] = event.day.date.toISOString()
        } else {
          defaults[name] = event.day.date.format('YYYY-MM-DD')
        }
      }
      this.$refs.rowCreateModal.show(defaults)
    },

    showRowContext(event, row) {
      this.selectedRow = row
      this.$refs.cardContext.toggleNextToMouse(event)
    },
    /**
     * Calls action in the store to refresh row directly from the backend - f. ex.
     * when editing row from a different table, when editing is complete, we need
     * to refresh the 'main' row that's 'under' the RowEdit modal.
     */
    refreshRow(row) {
      if (this.refreshingRow) {
        return
      }
      this.refreshingRow = true
      this.$nextTick(async () => {
        try {
          await this.$store.dispatch(
            this.storePrefix + 'view/calendar/refreshRowFromBackend',
            { table: this.table, row }
          )
        } catch (error) {
          notifyIf(error, 'row')
        } finally {
          this.refreshingRow = false
        }
      })
    },
    async deleteRow(row) {
      try {
        this.$refs.cardContext.hide()
        await this.$store.dispatch(
          this.storePrefix + 'view/calendar/deleteRow',
          {
            table: this.table,
            view: this.view,
            fields: this.fields,
            row,
          }
        )
        await this.$store.dispatch('toast/restore', {
          trash_item_type: 'row',
          parent_trash_item_id: this.table.id,
          trash_item_id: row.id,
        })
      } catch (error) {
        notifyIf(error, 'row')
      }
    },
  },
}
</script>
