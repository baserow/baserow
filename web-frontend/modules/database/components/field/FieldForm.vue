<template>
  <div v-auto-overflow-scroll class="context__form context__form--scrollable">
    <form class="context__form-container" @submit.prevent="submit">
      <FormGroup :error="fieldHasErrors('name')">
        <FormInput
          ref="name"
          v-model="values.name"
          :error="fieldHasErrors('name')"
          :placeholder="$t('fieldForm.name')"
          @blur="$v.values.name.$touch()"
          @input="isPrefilledWithSuggestedFieldName = false"
          @keydown.enter="handleKeydownEnter($event)"
        ></FormInput>
        <template #error>
          <span v-if="$v.values.name.$dirty && !$v.values.name.required">
            {{ $t('error.requiredField') }}
          </span>
          <span
            v-else-if="
              $v.values.name.$dirty && !$v.values.name.mustHaveUniqueFieldName
            "
          >
            {{ $t('fieldForm.fieldAlreadyExists') }}
          </span>
          <span
            v-else-if="
              $v.values.name.$dirty &&
              !$v.values.name.mustNotClashWithReservedName
            "
          >
            {{ $t('error.nameNotAllowed') }}
          </span>
          <span v-else-if="$v.values.name.$dirty && !$v.values.name.maxLength">
            {{ $t('error.nameTooLong') }}
          </span>
        </template>
      </FormGroup>

      <FormGroup v-if="forcedType === null" :error="$v.values.type.$error">
        <Dropdown
          ref="fieldTypesDropdown"
          v-model="values.type"
          :error="$v.values.type.$error"
          :fixed-items="true"
          :disabled="
            defaultValues.immutable_type || defaultValues.immutable_properties
          "
          @hide="$v.values.type.$touch()"
        >
          <DropdownItem
            v-for="(fieldType, type) in fieldTypes"
            :key="type"
            :icon="fieldType.iconClass"
            :name="fieldType.getName()"
            :alias="fieldType.getAlias()"
            :value="fieldType.type"
            :disabled="
              (primary && !fieldType.canBePrimaryField) ||
              !fieldType.isEnabled(workspace) ||
              fieldType.isDeactivated(workspace.id)
            "
            @click="clickOnDeactivatedItem($event, fieldType)"
          >
            <i class="select__item-icon" :class="fieldType.iconClass" />
            <span class="select__item-name-text" :title="fieldType.getName()">{{
              fieldType.getName()
            }}</span>
            <i
              v-if="fieldType.isDeactivated(workspace.id)"
              class="iconoir-lock"
            ></i>
            <component
              :is="fieldType.getDeactivatedClickModal(workspace.id)"
              :ref="'deactivatedClickModal-' + fieldType.type"
              :v-if="
                fieldType.isDeactivated(workspace.id) &&
                fieldType.getDeactivatedClickModal(workspace.id)
              "
              :name="$t(fieldType.getName())"
              :workspace="workspace"
            ></component>
          </DropdownItem>
        </Dropdown>

        <template #error> {{ $t('error.requiredField') }}</template>
      </FormGroup>

      <template v-if="hasFormComponent && !defaultValues.immutable_properties">
        <component
          :is="getFormComponent(values.type)"
          ref="childForm"
          :table="table"
          :field-type="values.type"
          :view="view"
          :primary="primary"
          :all-fields-in-table="allFieldsInTable"
          :name="values.name"
          :default-values="defaultValues"
          :database="database"
          @validate="$v.$touch"
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
    </form>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { required, maxLength } from 'vuelidate/lib/validators'
import FormTextarea from '@baserow/modules/core/components/FormTextarea'

import { getNextAvailableNameInSequence } from '@baserow/modules/core/utils/string'
import form from '@baserow/modules/core/mixins/form'
import {
  RESERVED_BASEROW_FIELD_NAMES,
  MAX_FIELD_NAME_LENGTH,
} from '@baserow/modules/database/utils/constants'

// @TODO focus form on open
export default {
  name: 'FieldForm',
  components: { FormTextarea },
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
  data() {
    return {
      allowedValues: ['name', 'type', 'description'],
      values: {
        name: '',
        type: this.forcedType || '',
        description: null,
      },
      isPrefilledWithSuggestedFieldName: false,
      oldValueType: null,
      showDescription: false,
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
    },
  },
  validations() {
    return {
      values: {
        name: {
          required,
          maxLength: maxLength(MAX_FIELD_NAME_LENGTH),
          mustHaveUniqueFieldName: this.mustHaveUniqueFieldName,
          mustNotClashWithReservedName: this.mustNotClashWithReservedName,
        },
        type: { required },
      },
    }
  },
  methods: {
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
    clickOnDeactivatedItem(event, fieldType) {
      if (fieldType.isDeactivated(this.workspace.id)) {
        this.$refs[`deactivatedClickModal-${fieldType.type}`][0].show()
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
  },
}
</script>
