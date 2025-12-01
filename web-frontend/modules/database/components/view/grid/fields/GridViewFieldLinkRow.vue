<template>
  <div
    v-prevent-parent-scroll
    class="grid-view__cell grid-field-many-to-many__cell active"
    :class="{ invalid: removingRelationships }"
  >
    <div class="grid-field-many-to-many__list">
      <component
        :is="publicGrid || !canAccessLinkedTable ? 'span' : 'a'"
        v-for="item in visibleValues"
        :key="item.id"
        class="grid-field-many-to-many__item"
        @click.prevent="showForeignRowModal(item)"
      >
        <span
          class="grid-field-many-to-many__name"
          :class="{
            'grid-field-link-row__unnamed':
              item.value === null || item.value === '',
          }"
          :title="item.value"
        >
          {{
            item.value || $t('gridViewFieldLinkRow.unnamed', { value: item.id })
          }}
        </span>
        <span
          v-if="itemLoadingId === item.id"
          class="grid-field-many-to-many__loading"
        ></span>
        <a
          v-else-if="!shouldFetchRow && canAccessLinkedTable"
          class="grid-field-many-to-many__remove"
          @click.prevent.stop="removeValue($event, value, item.id)"
        >
          <i class="iconoir-cancel"></i>
        </a>
      </component>
      <div
        v-if="shouldFetchRow && isFetchingRow"
        class="grid-field-many-to-many__item grid-field-many-to-many__item--loading"
      >
        <div class="loading"></div>
      </div>
      <a
        v-if="!shouldFetchRow && canAccessLinkedTable && canAddValue"
        class="grid-field-many-to-many__item grid-field-many-to-many__item--link"
        @click.prevent="showModal()"
      >
        <i class="iconoir-plus"></i>
      </a>
    </div>
    <div
      v-show="removingRelationships"
      class="grid-view__cell-error align-right"
    >
      {{ $t('gridViewFieldLinkRow.keepOnlyOneValue') }}
    </div>
    <SelectRowModal
      v-if="canAccessLinkedTable"
      ref="selectModal"
      :table-id="field.link_row_table_id"
      :new-row-presets="presetsForNewRowInLinkedTable"
      :view-id="field.link_row_limit_selection_view_id"
      :value="value"
      :multiple="field.link_row_multiple_relationships"
      :persistent-field-options-key="getPersistentFieldOptionsKey(field.id)"
      :store-prefix="storePrefix"
      @selected="addValue(value, $event)"
      @unselected="removeValue({}, value, $event.row.id)"
      @hidden="hideModal"
    ></SelectRowModal>
    <ForeignRowEditModal
      v-if="canAccessLinkedTable"
      ref="rowEditModal"
      :table-id="field.link_row_table_id"
      :fields-sortable="false"
      :can-modify-fields="false"
      :read-only="readOnly"
      :store-prefix="storePrefix"
      @hidden="hideModal"
      @refresh-row="$emit('refresh-row')"
    ></ForeignRowEditModal>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'

import { getPersistentFieldOptionsKey } from '@baserow/modules/database/utils/field'
import { isElement } from '@baserow/modules/core/utils/dom'
import gridField from '@baserow/modules/database/mixins/gridField'
import linkRowField from '@baserow/modules/database/mixins/linkRowField'
import arrayLoading from '@baserow/modules/database/mixins/arrayLoading'
import SelectRowModal from '@baserow/modules/database/components/row/SelectRowModal'
import ForeignRowEditModal from '@baserow/modules/database/components/row/ForeignRowEditModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import { isPrintableUnicodeCharacterKeyPress } from '@baserow/modules/core/utils/events'

export default {
  name: 'GridViewFieldLinkRow',
  components: { ForeignRowEditModal, SelectRowModal },
  mixins: [gridField, linkRowField, arrayLoading],
  data() {
    return {
      modalOpen: false,
      itemLoadingId: -1,
    }
  },
  computed: {
    // Return the reactive object that can be updated in runtime.
    workspace() {
      return this.$store.getters['workspace/get'](this.workspaceId)
    },
    canAccessLinkedTable() {
      const linkedTable = this.allTables.find(
        ({ id }) => id === this.field.link_row_table_id
      )

      if (!linkedTable) {
        return false
      }

      return (
        this.$hasPermission(
          'database.table.read',
          linkedTable,
          this.workspace.id
        ) && !this.readOnly
      )
    },
    allTables() {
      const databaseType = DatabaseApplicationType.getType()
      return this.$store.getters['application/getAll'].reduce(
        (tables, application) => {
          if (application.type === databaseType) {
            return tables.concat(application.tables || [])
          }
          return tables
        },
        []
      )
    },
  },
  beforeCreate() {
    this.$options.computed = {
      ...(this.$options.computed || {}),
      ...mapGetters({
        publicGrid: 'page/view/public/getIsPublic',
      }),
    }
  },
  methods: {
    getPersistentFieldOptionsKey(fieldId) {
      return getPersistentFieldOptionsKey(fieldId)
    },
    select() {
      // While the field is selected we want to open the select row toast by pressing
      // the enter key.
      this.$el.keydownEvent = (event) => {
        // If the tab or arrow keys are pressed we don't want to do anything because
        // the GridViewField component will select the next field.
        const ignoredKeys = [
          'Tab',
          'ArrowLeft',
          'ArrowUp',
          'ArrowRight',
          'ArrowDown',
        ]
        if (ignoredKeys.includes(event.key)) {
          return
        }

        // If the space bar key is pressed, we don't want to do anything because it
        // should open the row edit modal.
        if (event.key === ' ') {
          return
        }

        // When the enter key, or any printable character is pressed when not editing
        // the value we want to show the select row modal.
        if (
          !this.modalOpen &&
          (event.key === 'Enter' || isPrintableUnicodeCharacterKeyPress(event))
        ) {
          this.showModal()
        }
      }
      document.body.addEventListener('keydown', this.$el.keydownEvent)
    },
    beforeUnSelect() {
      document.body.removeEventListener('keydown', this.$el.keydownEvent)
    },
    /**
     * If the user clicks inside the select row or file modal we do not want to
     * unselect the field. The modals lives in the root of the body element and not
     * inside the cell, so the system naturally wants to unselect when the user clicks
     * inside one of these contexts.
     */
    canUnselectByClickingOutside(event) {
      if (!this.canAccessLinkedTable) {
        return true
      }

      const openModals = [
        ...this.$refs.selectModal.$refs.modal.moveToBody.children.map(
          (child) => child.$el
        ),
        this.$refs.selectModal.$el,
        ...this.$refs.rowEditModal.$refs.modal.$refs.modal.moveToBody.children.map(
          (child) => child.$el
        ),
        this.$refs.rowEditModal.$refs.modal.$el,
      ]

      return (
        // If the user clicks inside the select or row edit modal, we don't want to
        // allow unselecting.
        !openModals.some((modal) => {
          return isElement(modal, event.target)
        }) &&
        // If an element is not part of the body anymore, then it was deleted, and then
        // we don't have to unselect. This can for example happen when the user clicks
        // on something that will deleted because of it.
        document.body.contains(event.target)
      )
    },
    /**
     * Prevent unselecting the field cell by changing the event. Because the deleted
     * item is not going to be part of the dom anymore after deleting it will get
     * noticed as if the user clicked outside the cell which wasn't the case.
     */
    removeValue(event, value, id) {
      event.preventFieldCellUnselect = true
      return linkRowField.methods.removeValue.call(this, event, value, id)
    },
    showModal() {
      if (!this.canAccessLinkedTable || !this.canAddValue) {
        return
      }

      this.modalOpen = true
      this.$refs.selectModal.show()
    },
    hideModal() {
      this.modalOpen = false
    },
    /**
     * While the modal is open, all key combinations related to the field must be
     * ignored.
     */
    canSelectNext() {
      return !this.modalOpen
    },
    canKeyDown() {
      return !this.modalOpen
    },
    canKeyboardShortcut() {
      return !this.modalOpen
    },
    async showForeignRowModal(item) {
      // It's not possible to open the related row when the view is shared publicly
      // because the visitor doesn't have the right permissions.
      if (this.publicGrid || !this.canAccessLinkedTable) {
        return
      }

      this.itemLoadingId = item.id
      try {
        await this.$refs.rowEditModal.show(item.id)
        this.modalOpen = true
      } catch (error) {
        notifyIf(error)
      }
      this.itemLoadingId = -1
    },
  },
}
</script>
