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
        :error="fieldHasErrors('rollup_function')"
      >
        <Dropdown
          v-model="v$.values.rollup_function.$model"
          max-width
          :error="fieldHasErrors('rollup_function')"
          :fixed-items="true"
          @hide="v$.values.rollup_function.$touch()"
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
        ref="subForm"
        :default-values="subFormDefaultValues"
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
import { useVuelidate } from '@vuelidate/core'
import { required } from '@vuelidate/validators'

import form from '@baserow/modules/core/mixins/form'
import fieldSubForm from '@baserow/modules/database/mixins/fieldSubForm'
import lookupFieldSubForm from '@baserow/modules/database/mixins/lookupFieldSubForm'
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
  mixins: [form, fieldSubForm, lookupFieldSubForm],
  setup() {
    return { v$: useVuelidate({ $lazy: true }) }
  },
  data() {
    return {
      allowedValues: ['rollup_function'],
      values: {
        rollup_function: null,
      },
    }
  },
  computed: {
    rollupFunctions() {
      return Object.values(this.$registry.getAll('formula_function')).filter(
        (f) => f.isRollupCompatible(this.targetFieldFormulaType)
      )
    },
  },
  validations() {
    return {
      values: {
        rollup_function: { required },
      },
    }
  },
}
</script>
