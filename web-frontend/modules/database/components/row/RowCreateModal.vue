<template>
  <Modal ref="modal">
    <form @submit.prevent="create">
      <div class="box__title">
        <h2 class="row-modal__title">
          {{ heading }}
        </h2>
      </div>
      <Error :error="error"></Error>
      <RowEditModalFieldsList
        :primary-is-sortable="primaryIsSortable"
        :fields="visibleFields"
        :sortable="sortable"
        :hidden="false"
        :read-only="false"
        :row="row"
        :view="view"
        :table="table"
        :database="database"
        :can-modify-fields="canModifyFields"
        :all-fields-in-table="allFieldsInTable"
        @field-updated="$emit('field-updated', $event)"
        @field-deleted="$emit('field-deleted')"
        @order-fields="$emit('order-fields', $event)"
        @toggle-field-visibility="$emit('toggle-field-visibility', $event)"
        @update="update"
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
          :read-only="false"
          :row="row"
          :table="table"
          :view="view"
          :database="database"
          :can-modify-fields="canModifyFields"
          :all-fields-in-table="allFieldsInTable"
          @field-updated="$emit('field-updated', $event)"
          @field-deleted="$emit('field-deleted')"
          @toggle-field-visibility="$emit('toggle-field-visibility', $event)"
          @update="update"
        >
        </RowEditModalFieldsList>
      </RowEditModalHiddenFieldsSection>
      <div class="actions">
        <div class="align-right">
          <Button
            type="primary"
            size="large"
            :loading="loading"
            :disabled="loading"
          >
            {{ $t('action.create') }}
          </Button>
        </div>
      </div>
    </form>
  </Modal>
</template>

<script>
import Vue from 'vue'
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import RowEditModalFieldsList from './RowEditModalFieldsList.vue'
import RowEditModalHiddenFieldsSection from './RowEditModalHiddenFieldsSection.vue'
import { getPrimaryOrFirstField } from '@baserow/modules/database/utils/field'

export default {
  name: 'RowCreateModal',
  components: {
    RowEditModalFieldsList,
    RowEditModalHiddenFieldsSection,
  },
  mixins: [modal, error],
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
    primaryIsSortable: {
      type: Boolean,
      required: false,
      default: false,
    },
    sortable: {
      type: Boolean,
      required: false,
      default: true,
    },
    canModifyFields: {
      type: Boolean,
      required: false,
      default: true,
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
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    presets: {
      type: Object,
      required: false,
      default: () => ({}),
    },
  },
  data() {
    return {
      row: {},
      loading: false,
    }
  },
  computed: {
    allFields() {
      return this.visibleFields.concat(this.hiddenFields)
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
  },
  methods: {
    show(defaults = {}, ...args) {
      const row = {}
      this.allFields.forEach((field) => {
        const name = `field_${field.id}`
        if (this.presets[name] !== undefined) {
          row[name] = this.presets[name]
        } else {
          const fieldType = this.$registry.get('field', field._.type.type)
          row[name] = fieldType.getNewRowValue(field)
        }
      })
      Object.assign(row, defaults)
      Vue.set(this, 'row', row)
      return modal.methods.show.call(this, ...args)
    },
    update(event) {
      const name = `field_${event.field.id}`
      this.row[name] = event.value
    },
    create() {
      this.loading = true
      this.$emit('created', {
        row: this.row,
        callback: (error) => {
          if (error) {
            this.handleError(error)
          } else {
            this.hide()
          }
          this.loading = false
        },
      })
    },
  },
}
</script>
