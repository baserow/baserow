<template>
  <div class="context__form-container">
    <FormGroup
      small-label
      :label="$t('fieldType.formula')"
      required
      :error="!!error"
    >
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
import form from '@baserow/modules/core/mixins/form'

import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FormulaTypeSubForms from '@baserow/modules/database/components/formula/FormulaTypeSubForms'
import { FormulaFieldType } from '@baserow/modules/database/fieldTypes'

export default {
  name: 'FieldFormulaInitialSubForm',
  components: {
    FormulaTypeSubForms,
  },
  mixins: [form, fieldSubForm],
  props: {
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
