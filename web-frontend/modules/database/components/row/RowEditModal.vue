<template>
  <Modal
    ref="modal"
    :full-height="hasRightSidebar"
    :right-sidebar="hasRightSidebar"
    :content-scrollable="hasRightSidebar"
    :right-sidebar-scrollable="false"
    :collapsible-right-sidebar="true"
    @hidden="hidden"
  >
    <template #actions>
      <component
        :is="actionComponent"
        v-for="(actionComponent, i) in rowModalActionComponents"
        :key="i"
        :database="database"
        :table="table"
        :row="row"
      >
      </component>
    </template>
    <template #content>
      <div v-if="enableNavigation" class="row-edit-modal__navigation">
        <div v-if="navigationLoading" class="loading"></div>
        <template v-else>
          <a
            class="row-edit-modal__navigation-item"
            @click="$emit('navigate-previous', previousRow)"
          >
            <i class="iconoir-nav-arrow-up"></i>
          </a>
          <a
            class="row-edit-modal__navigation-item"
            @click="$emit('navigate-next', nextRow)"
          >
            <i class="iconoir-nav-arrow-down"></i>
          </a>
        </template>
      </div>
      <div class="box__title">
        <h2 class="row-modal__title">
          {{ heading }}
        </h2>
      </div>
      <RowEditModalFieldsList
        :primary-is-sortable="primaryIsSortable"
        :fields="visibleFields"
        :sortable="!readOnly && fieldsSortable"
        :can-modify-fields="!readOnly && canModifyFields"
        :hidden="false"
        :read-only="readOnly"
        :row="row"
        :view="view"
        :table="table"
        :database="database"
        :all-fields-in-table="allFieldsInTable"
        @field-updated="$emit('field-updated', $event)"
        @field-deleted="$emit('field-deleted')"
        @order-fields="$emit('order-fields', $event)"
        @toggle-field-visibility="$emit('toggle-field-visibility', $event)"
        @update="update"
        @refresh-row="$emit('refresh-row', $event)"
      ></RowEditModalFieldsList>
      <RowEditModalHiddenFieldsSection
        v-if="hiddenFields.length"
        :show-hidden-fields="showHiddenFields"
        @toggle-hidden-fields-visibility="
          $emit('toggle-hidden-fields-visibility')
        "
      >
        <RowEditModalFieldsList
          :primary-is-sortable="primaryIsSortable"
          :fields="hiddenFields"
          :sortable="false"
          :hidden="true"
          :read-only="readOnly"
          :row="row"
          :view="view"
          :table="table"
          :database="database"
          :all-fields-in-table="allFieldsInTable"
          @field-updated="$emit('field-updated', $event)"
          @field-deleted="$emit('field-deleted')"
          @toggle-field-visibility="$emit('toggle-field-visibility', $event)"
          @update="update"
          @refresh-row="$emit('refresh-row', $event)"
        >
        </RowEditModalFieldsList>
      </RowEditModalHiddenFieldsSection>
      <div
        v-if="
          !readOnly &&
          canModifyFields &&
          $hasPermission(
            'database.table.create_field',
            table,
            database.workspace.id
          )
        "
        class="actions"
      >
        <span ref="createFieldContextLink">
          <ButtonText
            tag="a"
            icon="iconoir-plus"
            @click="
              $refs.createFieldContext.toggle($refs.createFieldContextLink)
            "
          >
            {{ $t('rowEditModal.addField') }}
          </ButtonText></span
        >

        <CreateFieldContext
          ref="createFieldContext"
          :table="table"
          :view="view"
          :all-fields-in-table="allFieldsInTable"
          :database="database"
          @field-created="$emit('field-created', $event)"
          @field-created-callback-done="
            $emit('field-created-callback-done', $event)
          "
        ></CreateFieldContext>
      </div>
    </template>
    <template #sidebar>
      <RowEditModalSidebar
        :row="row"
        :table="table"
        :database="database"
        :fields="allFieldsInTable"
        :read-only="readOnly"
      ></RowEditModalSidebar>
    </template>
  </Modal>
</template>

<script>
import { mapGetters } from 'vuex'
import modal from '@baserow/modules/core/mixins/modal'
import CreateFieldContext from '@baserow/modules/database/components/field/CreateFieldContext'
import RowEditModalFieldsList from './RowEditModalFieldsList.vue'
import RowEditModalHiddenFieldsSection from './RowEditModalHiddenFieldsSection.vue'
import RowEditModalSidebar from './RowEditModalSidebar.vue'
import { getPrimaryOrFirstField } from '@baserow/modules/database/utils/field'

export default {
  name: 'RowEditModal',
  components: {
    CreateFieldContext,
    RowEditModalFieldsList,
    RowEditModalHiddenFieldsSection,
    RowEditModalSidebar,
  },
  mixins: [modal],
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
      type: [Object, null],
      required: false,
      default: null,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    primaryIsSortable: {
      type: Boolean,
      required: false,
      default: false,
    },
    visibleFields: {
      type: Array,
      required: true,
    },
    hiddenFields: {
      type: Array,
      required: false,
      default: () => [],
    },
    showHiddenFields: {
      type: Boolean,
      required: false,
      default: false,
    },
    rows: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    enableNavigation: {
      type: Boolean,
      required: false,
      default: false,
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
  },
  computed: {
    ...mapGetters({
      navigationLoading: 'rowModalNavigation/getLoading',
    }),
    modalRow() {
      return this.$store.getters['rowModal/get'](this._uid)
    },
    rowId() {
      return this.modalRow.id
    },
    rowExists() {
      return this.modalRow.exists
    },
    row() {
      return this.modalRow.row
    },
    rowIndex() {
      return this.rows.findIndex((r) => r !== null && r.id === this.rowId)
    },
    nextRow() {
      return this.rowIndex !== -1 && this.rows.length > this.rowIndex + 1
        ? this.rows[this.rowIndex + 1]
        : null
    },
    previousRow() {
      return this.rowIndex > 0 ? this.rows[this.rowIndex - 1] : null
    },
    heading() {
      const field = getPrimaryOrFirstField(this.visibleFields)

      if (!field) {
        return null
      }

      const name = `field_${field.id}`
      if (Object.prototype.hasOwnProperty.call(this.row, name)) {
        return this.$registry
          .get('field', field.type)
          .toHumanReadableString(field, this.row[name])
      } else {
        return null
      }
    },
    activeSidebarTypes() {
      const allSidebarTypes = this.$registry.getOrderedList('rowModalSidebar')
      return allSidebarTypes.filter(
        (type) =>
          type.isDeactivated(this.database, this.table, this.readOnly) ===
            false && type.getComponent()
      )
    },
    hasRightSidebar() {
      return this.activeSidebarTypes.length > 0
    },
    canSubscribeToRowUpdates() {
      return (
        this.$hasPermission(
          'database.table.listen_to_all',
          this.table,
          this.database.workspace.id
        ) &&
        // If the row ID is not an integer, it could mean that the row hasn't been
        // created in the backend yet.
        Number.isInteger(this.rowId)
      )
    },
    rowModalActionComponents() {
      return this.activeSidebarTypes
        .map((type) => type.getActionComponent(this.row))
        .filter((actionComponent) => actionComponent !== null)
    },
  },
  watch: {
    /**
     * It could happen that the view doesn't always have all the rows buffered. When
     * the modal is opened, it will find the correct row by looking through all the
     * rows of the view. If a filter changes, the existing row could be removed from the
     * buffer while the user still wants to edit the row because the modal is open. In
     * that case, we will keep a copy in the `rowModal` store, which will also listen
     * for real time update events to make sure the latest information is always
     * visible. If the buffer of the view changes and the row does exist, we want to
     * switch to that version to maintain reactivity between the two.
     */
    rows(value) {
      const row = value.find((r) => r !== null && r.id === this.rowId)
      if (row === undefined && this.rowExists) {
        this.$store.dispatch('rowModal/doesNotExist', {
          componentId: this._uid,
        })
      } else if (row !== undefined && !this.rowExists) {
        this.$store.dispatch('rowModal/doesExist', {
          componentId: this._uid,
          row,
        })
      } else if (row !== undefined) {
        // If the row already exists and it has changed, we need to replace it,
        // otherwise we might loose reactivity.
        this.$store.dispatch('rowModal/replace', {
          componentId: this._uid,
          row,
        })
      }
    },
    rowId(newValue, oldValue) {
      if (this.canSubscribeToRowUpdates) {
        if (oldValue > 0) {
          this.$realtime.unsubscribe('row', {
            table_id: this.table.id,
            row_id: oldValue,
          })
        }
        if (newValue > 0) {
          this.$realtime.subscribe('row', {
            table_id: this.table.id,
            row_id: newValue,
          })
        }
      }
    },
  },
  methods: {
    show(rowId, rowFallback = {}, ...args) {
      const row = this.rows.find((r) => r !== null && r.id === rowId)
      this.$store.dispatch('rowModal/open', {
        tableId: this.table.id,
        componentId: this._uid,
        id: rowId,
        row: row || rowFallback,
        exists: !!row,
      })
      if (this.canSubscribeToRowUpdates) {
        this.$realtime.subscribe('row', {
          table_id: this.table.id,
          row_id: rowId,
        })
      }
      this.getRootModal().show(...args)
    },
    hidden(...args) {
      if (this.canSubscribeToRowUpdates) {
        this.$realtime.unsubscribe('row', {
          table_id: this.table.id,
          row_id: this.rowId,
        })
      }
      this.$store.dispatch('rowModal/clear', { componentId: this._uid })
      this.$emit('hidden', { row: this.row })
    },
    /**
     * Because the modal can't update values by himself, an event will be called to
     * notify the parent component to actually update the value.
     */
    update(context) {
      context.table = this.table
      this.$emit('update', context)
    },
  },
}
</script>
