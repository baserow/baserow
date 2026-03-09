<template>
  <div class="form-view__sidebar">
    <div class="form-view__sidebar-fields">
      <div class="form-view__sidebar-fields-head">
        <div class="form-view__sidebar-fields-title">
          {{ $t('formSidebar.fields') }}
        </div>
        <ul
          v-if="!readOnly && !isDeactivated"
          class="form-view__sidebar-fields-actions"
        >
          <li v-if="fields.length > 0">
            <a
              @click="
                updateFieldOptionsOfFields(
                  view,
                  fields,
                  { enabled: true },
                  true
                )
              "
              >{{ $t('formSidebar.actions.addAll') }}</a
            >
          </li>
          <li v-if="enabledFields.length > 0">
            <a
              @click="
                updateFieldOptionsOfFields(
                  view,
                  enabledFields,
                  { enabled: false },
                  true
                )
              "
              >{{ $t('formSidebar.actions.removeAll') }}</a
            >
          </li>
        </ul>
      </div>
      <div v-if="fields.length > 0" class="form-view__sidebar-fields-list">
        <FormViewSidebarField
          v-for="field in fields"
          :key="field.id"
          v-sortable="{
            enabled: !readOnly && !isDeactivated,
            id: field.id,
            update: order,
          }"
          :field="field"
          :read-only="readOnly || isDeactivated"
          @updated-field-options="
            updateFieldOptionsOfField(view, field, $event)
          "
        >
        </FormViewSidebarField>
      </div>
      <p v-else class="form-view__sidebar-fields-description">
        {{ $t('formSidebar.fieldsDescription') }}
      </p>
      <div v-if="!readOnly && !isDeactivated">
        <span ref="createFieldContextLink">
          <ButtonText
            icon="iconoir-plus"
            @click="
              $refs.createFieldContext.toggle($refs.createFieldContextLink)
            "
          >
            {{ $t('formSidebar.actions.addField') }}
          </ButtonText>
        </span>
        <CreateFieldContext
          ref="createFieldContext"
          :table="table"
          :view="view"
          :all-fields-in-table="allFieldsInTable"
          :database="database"
          @field-created="$event.callback()"
        ></CreateFieldContext>
      </div>
      <div v-if="editableByFields.length > 0" class="margin-top-2">
        <p class="margin-bottom-1">
          <i class="iconoir-warning-circle"></i>
          {{ $t('formSidebar.rowEditableByDescription') }}
        </p>
        <div class="form-view__sidebar-fields-list">
          <div
            v-for="field in editableByFields"
            :key="field.id"
            class="form-view__sidebar-fields-item-wrapper"
          >
            <span
              class="form-view__sidebar-fields-item form-view__sidebar-fields-item--disabled"
            >
              <i
                class="form-view__sidebar-fields-icon"
                :class="field._.type.iconClass"
              ></i>
              <div class="form-view__sidebar-fields-name">
                {{ field.name }}
              </div>
            </span>
          </div>
        </div>
      </div>
    </div>
    <div class="form-view__sidebar-prefill-or-hide-link">
      <a @click="showFormPrefillOrHideModal">
        <i class="iconoir-chat-bubble-question"></i>
        {{ $t('formSidebar.prefillOrHideInfoLink') }}
      </a>
      <FormPrefillOrHideModal
        ref="formPrefillOrHideModal"
      ></FormPrefillOrHideModal>
    </div>
  </div>
</template>

<script>
import CreateFieldContext from '@baserow/modules/database/components/field/CreateFieldContext'
import formViewHelpers from '@baserow/modules/database/mixins/formViewHelpers'
import FormViewSidebarField from '@baserow/modules/database/components/view/form/FormViewSidebarField'
import FormPrefillOrHideModal from '@baserow/modules/database/components/view/form/FormPrefillOrHideModal'
import { FormViewEditRowFieldType } from '~/modules/database/fieldTypes.js'

export default {
  name: 'FormViewSidebar',
  components: {
    FormPrefillOrHideModal,
    CreateFieldContext,
    FormViewSidebarField,
  },
  mixins: [formViewHelpers],
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
    enabledFields: {
      type: Array,
      required: true,
    },
    readOnly: {
      type: Boolean,
      required: true,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
  },
  emits: ['ordered-fields'],
  computed: {
    modeType() {
      return this.$registry.get('formViewMode', this.view.mode)
    },
    isDeactivated() {
      return (
        !this.readOnly &&
        this.modeType.isDeactivated(this.database.workspace.id)
      )
    },
    editableByFields() {
      return this.fields.filter(
        (field) =>
          field.type === FormViewEditRowFieldType.getType() &&
          field.form_view_id === this.view.id
      )
    },
  },
  methods: {
    order(order) {
      this.$emit('ordered-fields', order)
    },
    showFormPrefillOrHideModal() {
      this.$refs.formPrefillOrHideModal.show()
    },
  },
}
</script>
