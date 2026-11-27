<template>
  <div class="context__form-container">
    <FormGroup
      data-kuma-scope
      small-label
      :label="$t('fieldType.formula')"
      required
      :error="!!error"
    >
      <template #label-action>
        <EditorPrompt
          :key="defaultValues.id"
          action="generate_formula"
          :label="fieldName"
          :workspace-id="database.workspace.id"
          :parameters="{
            table_id: table.id,
            field_id: defaultValues.id,
            field_name: fieldName,
            current: formula,
          }"
          @completed="$emit('update-formula', $event.formula)"
        />
      </template>
      <FormInput
        ref="formInput"
        :value="formula"
        monospace
        :loading="loading"
        :placeholder="$t('fieldFormulaInitialSubForm.formulaInputPlaceholder')"
        :focus-on-click="false"
        @click="$emit('open-advanced-context', $refs.formInput.$refs.input)"
        @input="$emit('open-advanced-context', $refs.formInput.$refs.input)"
      ></FormInput>

      <component
        :is="component"
        v-for="(component, index) in additionalInputComponents"
        :key="index"
        :database="database"
        :table="table"
        @update-formula="$emit('update-formula', $event)"
      ></component>

      <template v-if="!loading" #error
        ><div class="formula-field__error">{{ error }}</div></template
      >
      <template v-if="!loading">
        <a
          v-if="formulaTypeRefreshNeeded"
          class="formula-field__refresh-link"
          href="#"
          @click.stop="$emit('refresh-formula-type')"
        >
          <i class="iconoir-refresh-double"></i>
          {{ $t('fieldFormulaInitialSubForm.refreshFormulaOptions') }}
        </a>
      </template>
    </FormGroup>

    <template v-if="showTypeFormattingOptions">
      <FormulaTypeSubForms
        :default-values="defaultValues"
        :formula-type="formulaType"
        :table="table"
        :view="view"
        :all-fields-in-table="allFieldsInTable"
        :database="database"
        :primary="primary"
      >
      </FormulaTypeSubForms>
    </template>
  </div>
</template>
<script>
import EditorPrompt from '@baserow/modules/core/components/EditorPrompt'
import form from '@baserow/modules/core/mixins/form'

import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FormulaTypeSubForms from '@baserow/modules/database/components/formula/FormulaTypeSubForms'
import { FormulaFieldType } from '@baserow/modules/database/fieldTypes'

export default {
  name: 'FieldFormulaInitialSubForm',
  components: {
    EditorPrompt,
    FormulaTypeSubForms,
  },
  mixins: [form, fieldSubForm],
  props: {
    fieldName: { type: String, required: true },
    loading: {
      type: Boolean,
      required: true,
    },
    formula: {
      type: String,
      required: true,
    },
    formulaType: {
      type: String,
      required: false,
      default: null,
    },
    error: {
      type: String,
      required: false,
      default: null,
    },
    formulaTypeRefreshNeeded: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['open-advanced-context', 'refresh-formula-type', 'update-formula'],
  data() {
    return {
      allowedValues: [],
      values: {},
    }
  },
  computed: {
    showTypeFormattingOptions() {
      return !(this.loading || this.formulaTypeRefreshNeeded || this.error)
    },
    additionalInputComponents() {
      return this.$registry
        .get('field', FormulaFieldType.getType())
        .getAdditionalFormInputComponents()
    },
  },
}
</script>
