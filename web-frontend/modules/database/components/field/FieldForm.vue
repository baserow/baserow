<template>
  <div class="field-context__with-tabs-wrapper">
    <div class="field-context__tabs">
      <Tabs
        large
        :tab-items="[{ title: 'Basic' }, { title: 'Advanced' }]"
        :selected-index.sync="selectedTabIndex"
      ></Tabs>
    </div>
    <div v-auto-overflow-scroll class="context__form context__form--scrollable">
      <form @submit.prevent="beforeSubmit">
        <div v-show="selectedTabIndex === 0" class="context__form-container">
          <FormGroup :error="fieldHasErrors('name')">
            <FormInput
              ref="name"
              v-model="v$.values.name.$model"
              :error="fieldHasErrors('name')"
              :placeholder="$t('fieldForm.name')"
              @blur="v$.values.name.$touch()"
              @input="isPrefilledWithSuggestedFieldName = false"
              @keydown.enter="handleKeydownEnter($event)"
            ></FormInput>
            <template #error>
              {{ v$.values.name.$errors[0]?.$message }}
            </template>
          </FormGroup>

          <FormGroup v-if="forcedType === null" :error="fieldHasErrors('type')">
            <Dropdown
              ref="fieldTypesDropdown"
              v-model="v$.values.type.$model"
              :error="fieldHasErrors('type')"
              :fixed-items="true"
              :disabled="
                defaultValues.immutable_type ||
                defaultValues.immutable_properties
              "
              @hide="v$.values.type.$touch"
            >
              <DropdownItem
                v-for="(fieldType, type) in fieldTypes"
                :key="type"
                v-tooltip="
                  !fieldType.isDeactivated(workspace.id) &&
                  !fieldType.isEnabled(workspace)
                    ? fieldType.getDisabledTooltip(workspace)
                    : null
                "
                tooltip-position="top"
                :icon="fieldType.iconClass"
                :name="fieldType.getName()"
                :alias="fieldType.getAlias()"
                :value="fieldType.type"
                :disabled="
                  (primary && !fieldType.canBePrimaryField) ||
                  !fieldType.isEnabled(workspace) ||
                  fieldType.isDeactivated(workspace.id)
                "
                @click="clickOnItem($event, fieldType)"
              >
                <i class="select__item-icon" :class="fieldType.iconClass" />
                <span
                  class="select__item-name-text"
                  :title="fieldType.getName()"
                  >{{ fieldType.getName() }}</span
                >
                <i
                  v-if="fieldType.isDeactivated(workspace.id)"
                  class="iconoir-lock"
                ></i>
                <component
                  :is="
                    fieldType.getDeactivatedClickModal(workspace.id)
                      ? fieldType.getDeactivatedClickModal(workspace.id)[0]
                      : null
                  "
                  :ref="'deactivatedClickModal-' + fieldType.type"
                  :v-if="
                    fieldType.isDeactivated(workspace.id) &&
                    fieldType.getDeactivatedClickModal(workspace.id)
                  "
                  v-bind="
                    fieldType.getDeactivatedClickModal(workspace.id)
                      ? fieldType.getDeactivatedClickModal(workspace.id)[1]
                      : null
                  "
                  :workspace="workspace"
                ></component>
                <component
                  :is="
                    fieldType.getDisabledClickModal(workspace)
                      ? fieldType.getDisabledClickModal(workspace)[0]
                      : null
                  "
                  :ref="'disabledClickModal-' + fieldType.type"
                  :v-if="
                    !fieldType.isEnabled(workspace) &&
                    fieldType.getDisabledClickModal(workspace)
                  "
                  v-bind="
                    fieldType.getDisabledClickModal(workspace)
                      ? fieldType.getDisabledClickModal(workspace)[1]
                      : null
                  "
                  :workspace="workspace"
                ></component>
              </DropdownItem>
            </Dropdown>

            <template #error> {{ $t('error.requiredField') }}</template>
          </FormGroup>

          <template
            v-if="hasFormComponent && !defaultValues.immutable_properties"
          >
            <component
              :is="getFormComponent(values.type)"
              ref="childForm"
              :table="table"
              :field-type="values.type"
              :field-constraints="values.field_constraints"
              :view="view"
              :primary="primary"
              :all-fields-in-table="allFieldsInTable"
              :name="values.name"
              :default-values="defaultValues"
              :database="database"
              @validate="v$.$touch"
              @suggested-field-name="handleSuggestedFieldName($event)"
            />
          </template>
          <FormGroup
            v-if="showDescription"
            :error="fieldHasErrors('description')"
            :label="$t('fieldForm.description')"
            :small-label="true"
            required
          >
            <div class="control__elements">
              <FormTextarea
                ref="description"
                v-model="values.description"
                :min-rows="1"
                :max-rows="16"
                auto-expandable
                :placeholder="$t('fieldForm.description')"
                size="small"
              />
            </div>
          </FormGroup>
        </div>
        <div v-show="selectedTabIndex === 1" class="context__form-container">
          <FieldConstraintsSubForm
            v-model="values.field_constraints"
            :field="fieldForConstraints"
            :disabled="defaultValues.immutable_properties"
            :error="fieldConstraintError"
            :field-default-value="fieldDefaultValue"
          />

          <FormGroup
            :label="$t('fieldForm.dbIndex')"
            :small-label="true"
            :horizontal="true"
            required
          >
            <div class="control__elements flex justify-content-end">
              <SwitchInput
                v-tooltip="
                  !canHaveDbIndex
                    ? $t('fieldForm.dbIndexDisabledTooltip')
                    : null
                "
                :value="!!canHaveDbIndex && values.db_index"
                :small="true"
                :disabled="!canHaveDbIndex"
                class="inline-flex"
                @input="values.db_index = $event"
              ></SwitchInput>
            </div>
          </FormGroup>
          <div class="control__messages padding-top-0">
            <p
              v-if="dbIndexError"
              class="control__messages--error field-context__inner-element-width"
            >
              {{ $t('fieldForm.dbIndexError') }}
            </p>
            <p class="control__helper-text field-context__inner-element-width">
              {{ $t('fieldForm.dbIndexDescription') }}
            </p>
          </div>
        </div>
      </form>
    </div>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { required, maxLength, helpers } from '@vuelidate/validators'
import FormTextarea from '@baserow/modules/core/components/FormTextarea'
import { useVuelidate } from '@vuelidate/core'
import FieldConstraintsSubForm from '@baserow/modules/database/components/field/FieldConstraintsSubForm'

import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import form from '@baserow/modules/core/mixins/form'
import {
  RESERVED_BASEROW_FIELD_NAMES,
  MAX_FIELD_NAME_LENGTH,
} from '@baserow/modules/database/utils/constants'
import { FIELD_CONSTRAINT_ERROR_CODES } from '@baserow/modules/database/constants'

// @TODO focus form on open
export default {
  name: 'FieldForm',
  components: { FormTextarea, FieldConstraintsSubForm },
  mixins: [form],
  props: {
    table: {
      type: Object,
      required: true,
    },
    view: {
      type: [Object, null],
      required: false,
      default: null,
    },
    primary: {
      type: Boolean,
      required: false,
      default: false,
    },
    forcedType: {
      type: [String, null],
      required: false,
      default: null,
    },
    allFieldsInTable: {
      type: Array,
      required: true,
    },
    database: {
      type: Object,
      required: true,
    },
  },
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: [
        'name',
        'type',
        'description',
        'db_index',
        'field_constraints',
      ],
      values: {
        name: this.defaultValues.name,
        type: this.forcedType || this.defaultValues.type,
        description: this.defaultValues.description,
        db_index: this.defaultValues.db_index,
        field_constraints: this.defaultValues.field_constraints || [],
      },
      isPrefilledWithSuggestedFieldName: false,
      oldValueType: null,
      showDescription: false,
      selectedTabIndex: 0,
      dbIndexError: false,
      fieldConstraintError: null,
    }
  },
  computed: {
    // Return the reactive object that can be updated in runtime.
    workspace() {
      return this.$store.getters['workspace/get'](this.database.workspace.id)
    },
    fieldTypes() {
      return this.$registry.getAll('field')
    },
    hasFormComponent() {
      return !!this.values.type && this.getFormComponent(this.values.type)
    },
    existingFieldId() {
      return this.defaultValues ? this.defaultValues.id : null
    },
    canHaveDbIndex() {
      if (!this.values.type) {
        return false
      }

      const values = Object.assign({}, this.defaultValues, this.values)
      return this.$registry.get('field', values.type).canHaveDbIndex(values)
    },
    fieldForConstraints() {
      return {
        type: this.values.type,
        ...this.defaultValues,
        ...this.values,
      }
    },
    ...mapGetters({
      fields: 'field/getAll',
    }),
    isNameFieldEmptyOrPrefilled() {
      return (
        this.values.name === '' ||
        this.values.name ===
          this.getNextAvailableFieldName(
            this.fieldTypes[this.oldValueType]?.getName()
          ) ||
        this.values.name ===
          this.getNextAvailableFieldName(
            this.fieldTypes[this.values.type]?.getName()
          ) ||
        this.isPrefilledWithSuggestedFieldName
      )
    },
    fieldDefaultValue() {
      if (!this.values.type) return null

      const fieldTypeClass = this.$registry.get('field', this.values.type)
      const defaultValueFieldName = fieldTypeClass.getDefaultValueFieldName()
      return this.getFormValues()[defaultValueFieldName] || null
    },
  },
  watch: {
    // if the name field is empty or prefilled by a default value
    // we want to update the name field with the name of the field type
    // when the field type is changed.
    'values.type'(newValueType, oldValueType) {
      this.oldValueType = oldValueType
      if (this.isNameFieldEmptyOrPrefilled) {
        const availableFieldName = this.getNextAvailableFieldName(
          this.fieldTypes[newValueType]?.getName()
        )
        this.values.name = availableFieldName
      }
      this.isPrefilledWithSuggestedFieldName = false

      this.findAndSetCompatibleConstraints(newValueType)
    },
    // Clear constraint error when constraints are modified
    'values.field_constraints'() {
      if (this.fieldConstraintError) {
        this.fieldConstraintError = null
      }
    },
  },
  validations() {
    return {
      values: {
        name: {
          required: helpers.withMessage(
            this.$t('error.requiredField'),
            required
          ),
          maxLength: helpers.withMessage(
            this.$t('fieldForm.nameTooLong'),
            maxLength(MAX_FIELD_NAME_LENGTH)
          ),
          mustHaveUniqueFieldName: helpers.withMessage(
            this.$t('fieldForm.fieldAlreadyExists'),
            this.mustHaveUniqueFieldName
          ),
          mustNotClashWithReservedName: helpers.withMessage(
            this.$t('fieldForm.nameNotAllowed'),
            this.mustNotClashWithReservedName
          ),
        },
        type: { required },
      },
    }
  },
  methods: {
    async submit(deep) {
      this.dbIndexError = false
      this.fieldConstraintError = null
      await form.methods.submit.bind(this)(deep)
    },
    showDbIndexError() {
      this.selectedTabIndex = 1
      this.dbIndexError = true
    },
    mustHaveUniqueFieldName(param) {
      let fields = this.fields
      if (this.existingFieldId !== null) {
        fields = fields.filter((f) => f.id !== this.existingFieldId)
      }
      return !fields.map((f) => f.name).includes(param?.trim())
    },
    mustNotClashWithReservedName(param) {
      return !RESERVED_BASEROW_FIELD_NAMES.includes(param?.trim())
    },
    getFormComponent(type) {
      const fieldType = this.$registry.get('field', type)
      if (fieldType.isEnabled(this.workspace)) {
        return fieldType.getFormComponent()
      }
    },
    showFieldTypesDropdown(target) {
      this.$refs.fieldTypesDropdown.show(target)
    },
    handleSuggestedFieldName(event) {
      if (this.isNameFieldEmptyOrPrefilled) {
        this.isPrefilledWithSuggestedFieldName = true
        const availableFieldName = this.getNextAvailableFieldName(event)
        this.values.name = availableFieldName
      }
    },
    getNextAvailableFieldName(baseName) {
      const excludeNames = this.fields.map((f) => f.name)
      return getNextAvailableNameInSequence(baseName, excludeNames)
    },
    handleKeydownEnter(event) {
      event.preventDefault()
      this.$emit('keydown-enter')
      this.submit()
    },
    clickOnItem(event, fieldType) {
      if (fieldType.isDeactivated(this.workspace.id)) {
        this.$refs[`deactivatedClickModal-${fieldType.type}`][0].show()
      } else if (!fieldType.isEnabled(this.workspace)) {
        this.$refs[`disabledClickModal-${fieldType.type}`][0].show()
      }
    },
    /**
     * This sets the showDescription flag to display description text editor, even
     * if values.description is empty.
     *
     * Used by parent components.
     */
    showDescriptionField() {
      this.showDescription = true
      this.selectedTabIndex = 0
      this.$nextTick(() => {
        this.$refs.description.focus()
      })
    },
    /**
     * Helper method to get information if description is not empty.
     * Used by parent components
     */
    isDescriptionFieldNotEmpty() {
      this.showDescription = !!this.values.description
      return this.showDescription
    },
    getFormValues() {
      // Only set the `db_index` to true if the frontend knows for certain that the
      // field type is supported.
      return Object.assign({}, this.values, this.getChildFormsValues(), {
        db_index: this.canHaveDbIndex && this.values.db_index,
      })
    },
    handleErrorByForm(error) {
      let handled = form.methods.handleErrorByForm.bind(this)(error)

      if (
        error.handler &&
        error.handler.code === 'ERROR_DB_INDEX_NOT_SUPPORTED'
      ) {
        this.showDbIndexError()
        handled = true
      }

      if (
        error.handler &&
        FIELD_CONSTRAINT_ERROR_CODES.includes(error.handler.code)
      ) {
        this.selectedTabIndex = 1
        this.fieldConstraintError = error.handler.code
        handled = true
      }

      return handled
    },

    findAndSetCompatibleConstraints(newFieldType) {
      if (
        !this.values.field_constraints ||
        this.values.field_constraints.length === 0
      ) {
        return
      }

      const compatibleConstraints = this.values.field_constraints
        .map((constraint) => {
          if (!constraint.type_name) {
            return null
          }

          const compatibleConstraintType = this.$registry.getSpecificConstraint(
            'fieldConstraint',
            constraint.type_name,
            newFieldType
          )

          if (compatibleConstraintType) {
            return { ...constraint }
          }

          return null
        })
        .filter(Boolean)

      if (
        compatibleConstraints.length !== this.values.field_constraints.length
      ) {
        this.$emit('input', compatibleConstraints)
        this.values.field_constraints = compatibleConstraints
        this.fieldConstraintError = null
      }
    },
  },
}
</script>
