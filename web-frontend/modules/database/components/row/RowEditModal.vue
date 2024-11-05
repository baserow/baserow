<template>
  <ModalV2
    ref="modal"
    :full-height="hasRightSidebar"
    :right-sidebar="hasRightSidebar"
    sidebar-no-scroll
    :footer="false"
    :header="false"
    topbar
    @hidden="hidden"
  >
    <template #topbar-content>
      <div class="row-edit-modal__navigation">
        <div
          v-if="navigationLoading"
          class="row-edit-modal__navigation-loading"
        >
          <span class="loading"> </span>
        </div>
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

        <span class="row-edit-modal__heading">
          {{ $t('localBaserowGetRowForm.rowFieldLabel') }}:
          <strong v-if="!loading">{{ row.id }}</strong>
        </span>
      </div>
    </template>

    <template #topbar-actions>
      <component
        :is="actionComponent"
        v-for="(actionComponent, i) in rowModalActionComponents"
        :key="i"
        :database="database"
        :table="table"
        :row="row"
      >
      </component>

      <li
        v-if="hasRightSidebar"
        class="modal__topbar-icon"
        :class="{ 'modal__topbar-icon--active': !collapseSidebar }"
        @click="handleCollapseSidebar"
      >
        <i class="iconoir-message-text"></i>
      </li>

      <li
        v-if="!readOnly && displayRowActions"
        ref="contextMoreLink"
        class="modal__topbar-icon"
        @click="
          $refs.moreContext.toggle($refs.contextMoreLink, 'bottom', 'right', 0)
        "
      >
        <i class="baserow-icon-more-vertical"></i>
      </li>

      <Context ref="moreContext">
        <ul class="context__menu">
          <li class="context__menu-item">
            <a
              class="context__menu-item-link js-ctx-delete-row"
              @click="handleRowDuplicate"
            >
              <i class="context__menu-item-icon iconoir-copy"></i>
              {{ $t('gridView.duplicateRow') }}
            </a>
          </li>

          <li class="context__menu-item context__menu-item--with-separator">
            <a
              class="context__menu-item-link context__menu-item-link--delete js-ctx-delete-row"
              :class="{ 'context__menu-item-link--loading': loadingDeleteRow }"
              @click="$emit('delete-row', row)"
            >
              <i class="context__menu-item-icon iconoir-bin"></i>
              {{ $t('gridView.deleteRow') }}
            </a>
          </li>
        </ul>
      </Context>
    </template>

    <template #content>
      <div v-if="loading" class="loading-absolute-center" />

      <template v-else>
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
              type="secondary"
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
    </template>

    <template #sidebar-content>
      <RowEditModalSidebar
        v-if="!loading"
        :row="row"
        :table="table"
        :database="database"
        :fields="allFieldsInTable"
        :read-only="readOnly"
      ></RowEditModalSidebar>
    </template>
  </ModalV2>
</template>

<script>
import { mapGetters } from 'vuex'
import modalv2 from '@baserow/modules/core/mixins/modalv2'
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
  mixins: [modalv2],

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
    displayRowActions: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      collapseSidebar: false,
      loading: false,
      loadingDeleteRow: false,
    }
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
    handleCollapseSidebar() {
      this.collapseSidebar = !this.collapseSidebar
      this.$refs.modal.collapseRightSidebar()
    },
    handleRowDuplicate() {
      this.$refs.moreContext.hide()
      this.loading = true
      this.$emit('duplicate-row', this.row)
    },
    navigateToNextRow() {
      this.$emit('navigate-next', this.nextRow)
      this.loading = false
    },
    toggleLoadingDeleteRow() {
      this.loadingDeleteRow = !this.loadingDeleteRow
    },
  },
}
</script>
