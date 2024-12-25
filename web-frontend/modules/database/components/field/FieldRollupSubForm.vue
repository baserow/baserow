<template>
  <div class="context__form-container">
    <FieldSelectThroughFieldSubForm
      :fields="allFieldsInTable"
      :database="database"
      :default-values="defaultValues"
      @input="selectedThroughField = $event"
    ></FieldSelectThroughFieldSubForm>
    <FieldSelectTargetFieldSubForm
      :database="database"
      :table="table"
      :through-field="selectedThroughField"
      :default-values="defaultValues"
      :label="$t('fieldRollupSubForm.selectTargetFieldLabel')"
      @input="selectedTargetField = $event"
    ></FieldSelectTargetFieldSubForm>
    <template v-if="selectedTargetField">
      <FormGroup
        required
        small-label
        :label="$t('fieldRollupSubForm.label')"
        :error="$v.values.rollup_function.$error"
      >
        <Dropdown
          v-model="values.rollup_function"
          max-width
          :error="$v.values.rollup_function.$error"
          :fixed-items="true"
          @hide="$v.values.rollup_function.$touch()"
        >
          <DropdownItem
            v-for="f in rollupFunctions"
            :key="f.getType()"
            :name="f.getType()"
            :value="f.getType()"
            :description="f.getDescription()"
          ></DropdownItem>
        </Dropdown>
      </FormGroup>

      <FormulaTypeSubForms
        :default-values="defaultValues"
        :formula-type="targetFieldFormulaType"
        :table="table"
        :view="view"
        :all-fields-in-table="allFieldsInTable"
        :database="database"
      >
      </FormulaTypeSubForms>
    </template>
    <div v-if="errorFromServer" class="error formula-field__error">
      {{ errorFromServer }}
    </div>
  </div>
</template>

<script>
import { required } from 'vuelidate/lib/validators'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import FormulaTypeSubForms from '@baserow/modules/database/components/formula/FormulaTypeSubForms'
import FieldSelectThroughFieldSubForm from '@baserow/modules/database/components/field/FieldSelectThroughFieldSubForm'
import FieldSelectTargetFieldSubForm from '@baserow/modules/database/components/field/FieldSelectTargetFieldSubForm'

export default {
  name: 'FieldRollupSubForm',
  components: {
    FieldSelectThroughFieldSubForm,
    FieldSelectTargetFieldSubForm,
    FormulaTypeSubForms,
  },
  mixins: [form, fieldSubForm],
  data() {
    return {
      selectedThroughField: null,
      selectedTargetField: null,
      allowedValues: ['rollup_function'],
      values: {
        rollup_function: null,
      },
      errorFromServer: null,
    }
  },
  computed: {
    targetFieldFormulaType() {
      if (this.selectedTargetField) {
        return (
          this.selectedTargetField.array_formula_type ||
          this.selectedTargetField.type
        )
      }
      return 'unknown'
    },
    rollupFunctions() {
      return Object.values(this.$registry.getAll('formula_function')).filter(
        (f) => f.isRollupCompatible(this.targetFieldFormulaType)
      )
    },
  },
  validations: {
    values: {
      rollup_function: { required },
    },
  },
  methods: {
    handleErrorByForm(error) {
      if (
        [
          'ERROR_WITH_FORMULA',
          'ERROR_FIELD_SELF_REFERENCE',
          'ERROR_FIELD_CIRCULAR_REFERENCE',
        ].includes(error.handler.code)
      ) {
        this.errorFromServer = error.handler.detail
        return true
      } else {
        return false
      }
    },
    reset() {
      form.methods.reset.call(this)
      this.errorFromServer = null
    },
  },
}
</script>
