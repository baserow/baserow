<template>
  <div v-if="singleSelectField === null" class="kanban-view__stacked-by-page">
    <KanbanViewStackedBy
      :table="table"
      :view="view"
      :fields="fields"
      :database="database"
      :read-only="readOnly"
      :store-prefix="storePrefix"
      :include-field-options-on-refresh="true"
      @refresh="$emit('refresh', $event)"
    ></KanbanViewStackedBy>
  </div>
  <div
    v-else
    ref="kanban"
    v-auto-scroll="{
      orientation: 'horizontal',
      enabled: () => draggingRow !== null,
      speed: 6,
      padding: 12,
    }"
    class="kanban-view"
  >
    <div class="kanban-view__stacks">
      <KanbanViewStack
        :database="database"
        :table="table"
        :view="view"
        :card-fields="cardFields"
        :fields="fields"
        :read-only="readOnly"
        :store-prefix="storePrefix"
        @create-row="openCreateRowModal"
        @edit-row="openRowEditModal($event)"
        @refresh="$emit('refresh', $event)"
        @row-context="showRowContext($event.event, $event.row)"
      ></KanbanViewStack>
      <KanbanViewStack
        v-for="option in existingSelectOption"
        :key="option.id"
        :option="option"
        :database="database"
        :table="table"
        :view="view"
        :card-fields="cardFields"
        :fields="fields"
        :read-only="readOnly"
        :store-prefix="storePrefix"
        @create-row="openCreateRowModal"
        @edit-row="openRowEditModal($event)"
        @refresh="$emit('refresh', $event)"
        @row-context="showRowContext($event.event, $event.row)"
      ></KanbanViewStack>
      <div class="kanban-view__stack-wrapper">
        <div class="kanban-view__stack">
          <div class="kanban-view__stack-head">
            <Button
              v-if="
                !readOnly &&
                !singleSelectField.immutable_properties &&
                $hasPermission(
                  'database.table.field.update',
                  table,
                  database.workspace.id
                )
              "
              ref="addOptionContextLink"
              tag="a"
              type="secondary"
              size="regular"
              icon="iconoir-plus"
              :full-width="true"
              @click="
                $refs.addOptionContext.toggle(
                  $refs.addOptionContextLink.$el,
                  'bottom',
                  'right'
                )
              "
              >{{ $t('kanbanView.addStack') }}</Button
            >
            <KanbanViewCreateStackContext
              ref="addOptionContext"
              :fields="fields"
              :store-prefix="storePrefix"
            ></KanbanViewCreateStackContext>
          </div>
        </div>
      </div>
    </div>
    <RowCreateModal
      ref="rowCreateModal"
      :database="database"
      :table="table"
      :view="view"
      :primary-is-sortable="true"
      :visible-fields="cardFields"
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
      :primary-is-sortable="true"
      :visible-fields="cardFields"
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
      @refresh-row="refreshRow"
    ></RowEditModal>
    <Context
      ref="cardContext"
      :overflow-scroll="true"
      :max-height-if-outside-viewport="true"
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
import { mapGetters } from 'vuex'
import { clone } from '@baserow/modules/core/utils/object'
import { populateRow } from '@baserow/modules/database/store/view/grid'
import { notifyIf } from '@baserow/modules/core/utils/error'
import viewHelpers from '@baserow/modules/database/mixins/viewHelpers'
import {
  sortFieldsByOrderAndIdFunction,
  filterVisibleFieldsFunction,
  filterHiddenFieldsFunction,
} from '@baserow/modules/database/utils/view'
import RowCreateModal from '@baserow/modules/database/components/row/RowCreateModal'
import RowEditModal from '@baserow/modules/database/components/row/RowEditModal'
import kanbanViewHelper from '@baserow_premium/mixins/kanbanViewHelper'
import KanbanViewStack from '@baserow_premium/components/views/kanban/KanbanViewStack'
import KanbanViewStackedBy from '@baserow_premium/components/views/kanban/KanbanViewStackedBy'
import KanbanViewCreateStackContext from '@baserow_premium/components/views/kanban/KanbanViewCreateStackContext'

export default {
  name: 'KanbanView',
  components: {
    RowCreateModal,
    RowEditModal,
    KanbanViewCreateStackContext,
    KanbanViewStackedBy,
    KanbanViewStack,
  },
  mixins: [viewHelpers, kanbanViewHelper],
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
  },
  data() {
    return {
      showHiddenFieldsInRowModal: false,
      selectedRow: null,
    }
  },
  computed: {
    ...mapGetters({
      row: 'rowModalNavigation/getRow',
    }),
    /**
     * Returns the visible field objects in the right order.
     */
    cardFields() {
      const fieldOptions = this.fieldOptions
      return this.fields
        .filter(filterVisibleFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    hiddenFields() {
      const fieldOptions = this.fieldOptions
      return this.fields
        .filter(filterHiddenFieldsFunction(fieldOptions))
        .sort(sortFieldsByOrderAndIdFunction(fieldOptions))
    },
    /**
     * Returns the single select field object that the kanban view uses to workspace the
     * cards in stacks.
     */
    singleSelectField() {
      const allFields = this.fields
      for (let i = 0; i < allFields.length; i++) {
        if (allFields[i].id === this.singleSelectFieldId) {
          return allFields[i]
        }
      }
      return null
    },
    existingSelectOption() {
      return this.singleSelectField.select_options.filter((option) => {
        return this.$store.getters[
          this.$options.propsData.storePrefix + 'view/kanban/stackExists'
        ](option.id)
      })
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
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        singleSelectFieldId:
          this.$options.propsData.storePrefix +
          'view/kanban/getSingleSelectFieldId',
        allRows: this.$options.propsData.storePrefix + 'view/kanban/getAllRows',
        draggingRow:
          this.$options.propsData.storePrefix + 'view/kanban/getDraggingRow',
      }),
    }
  },
  mounted() {
    if (this.row !== null) {
      this.populateAndEditRow(this.row)
    }
  },
  methods: {
    /**
     * When the row edit modal is opened we notify
     * the Table component that a new row has been selected,
     * such that we can update the path to include the row id.
     */
    openRowEditModal(row) {
      this.$refs.rowEditModal.show(row.id)
      this.$emit('selected-row', row)
    },
    openCreateRowModal(event) {
      const defaults = {}
      const name = `field_${this.singleSelectField.id}`
      if (event.option !== null) {
        defaults[name] = clone(event.option)
      } else {
        defaults[name] = null
      }

      this.$refs.rowCreateModal.show(defaults)
    },
    async createRow({ row, callback }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/kanban/createNewRow',
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
    async updateValue({ field, row, value, oldValue }) {
      try {
        await this.$store.dispatch(
          this.storePrefix + 'view/kanban/updateRowValue',
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
            this.storePrefix + 'view/kanban/refreshRowFromBackend',
            { table: this.table, row }
          )
        } catch (error) {
          notifyIf(error, 'row')
        } finally {
          this.refreshingRow = false
        }
      })
    },
    /**
     * Populates a new row and opens the row edit modal
     * to edit the row.
     */
    populateAndEditRow(row) {
      const rowClone = populateRow(clone(row))
      this.$refs.rowEditModal.show(row.id, rowClone)
    },

    showRowContext(event, row) {
      this.selectedRow = row
      this.$refs.cardContext.toggleNextToMouse(event)
    },

    async deleteRow(row) {
      try {
        this.$refs.cardContext.hide()
        await this.$store.dispatch(
          this.storePrefix + 'view/kanban/deleteExistingRow',
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
