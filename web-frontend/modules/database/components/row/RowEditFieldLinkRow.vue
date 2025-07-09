<template>
  <div class="control__elements">
    <ul class="field-link-row__items">
      <li
        v-for="item in visibleValues"
        :key="item.id"
        class="field-link-row__item"
      >
        <component
          :is="readOnly || isInForeignRowEditModal ? 'span' : 'a'"
          class="field-link-row__name"
          :class="{
            'field-link-row__name--unnamed':
              item.value === null || item.value === '',
          }"
          @click.prevent="showForeignRowModal(item)"
        >
          {{ item.value || 'unnamed row ' + item.id }}
        </component>
        <span
          v-if="itemLoadingId === item.id"
          class="field-link-row__loading"
        ></span>
        <a
          v-else-if="!shouldFetchRow && !readOnly"
          class="field-link-row__remove"
          @click.prevent.stop="removeValue($event, value, item.id)"
        >
          <i class="iconoir-cancel"></i>
        </a>
      </li>
      <li
        v-if="shouldFetchRow && isFetchingRow"
        class="field-link-row__item field-link-row__item--loading"
      >
        <div class="loading"></div>
      </li>
    </ul>
    <a
      v-if="!shouldFetchRow && !readOnly && canAddValue"
      class="add"
      @click.prevent="$refs.selectModal.show()"
    >
      <i class="iconoir-plus add__icon"></i>
      {{ $t('rowEditFieldLinkRow.addLink') }}
    </a>
    <div v-show="removingRelationships" class="error">
      {{ $t('rowEditFieldLinkRow.keepOnlyOneValue') }}
    </div>
    <div v-show="touched && !valid" class="error">
      {{ error }}
    </div>
    <SelectRowModal
      v-if="!readOnly"
      ref="selectModal"
      :table-id="field.link_row_table_id"
      :view-id="field.link_row_limit_selection_view_id"
      :value="value"
      :multiple="field.link_row_multiple_relationships"
      :new-row-presets="presetsForNewRowInLinkedTable"
      :persistent-field-options-key="getPersistentFieldOptionsKey(field.id)"
      @selected="addValue(value, $event)"
      @unselected="removeValue({}, value, $event.row.id)"
    ></SelectRowModal>
    <ForeignRowEditModal
      v-if="!readOnly || isInForeignRowEditModal"
      ref="rowEditModal"
      :table-id="field.link_row_table_id"
      :fields-sortable="false"
      :can-modify-fields="false"
      :read-only="readOnly"
      @hidden="modalOpen = false"
      @refresh-row="$emit('refresh-row')"
    ></ForeignRowEditModal>
  </div>
</template>

<script>
import { getPersistentFieldOptionsKey } from '@baserow/modules/database/utils/field'
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import arrayLoading from '@baserow/modules/database/mixins/arrayLoading'
import linkRowField from '@baserow/modules/database/mixins/linkRowField'
import SelectRowModal from '@baserow/modules/database/components/row/SelectRowModal'
import ForeignRowEditModal from '@baserow/modules/database/components/row/ForeignRowEditModal'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  components: { SelectRowModal, ForeignRowEditModal },
  mixins: [rowEditField, linkRowField, arrayLoading],
  data() {
    return {
      itemLoadingId: -1,
    }
  },
  computed: {
    /**
     * If this component is a child of the `ForeignRowEditModal`, then we don't want to
     * open another ForeignRowEditModal when clicking on a relationship. This is because
     * we don't support that yet. Mainly because of real-time collaboration reasons.
     */
    isInForeignRowEditModal() {
      let parent = this.$parent
      while (parent !== undefined) {
        if (parent.$options.name === ForeignRowEditModal.name) {
          return true
        }
        parent = parent.$parent
      }
      return false
    },
  },
  methods: {
    getPersistentFieldOptionsKey(fieldId) {
      return getPersistentFieldOptionsKey(fieldId)
    },
    removeValue(...args) {
      linkRowField.methods.removeValue.call(this, ...args)
      this.touch()
    },
    addValue(...args) {
      linkRowField.methods.addValue.call(this, ...args)
      this.touch()
    },
    async showForeignRowModal(item) {
      if (this.readOnly || this.isInForeignRowEditModal) {
        return
      }

      this.itemLoadingId = item.id
      try {
        await this.$refs.rowEditModal.show(item.id)
      } catch (error) {
        notifyIf(error)
      }
      this.itemLoadingId = -1
    },
  },
}
</script>
