<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('generalForm.valueTitle')"
      class="margin-bottom-2"
      :required="true"
    >
      <InjectedFormulaInput
        v-model="values.value"
        :placeholder="$t('generalForm.valuePlaceholder')"
      />
    </FormGroup>
    <RatingFormFields
      :default-values="defaultValues"
      :color-variables="colorVariables"
      @values-changed="emitChange"
    />
  </form>
</template>

<script>
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import FormGroup from '@baserow/modules/core/components/FormGroup'
import RatingFormFields from '@baserow/modules/builder/components/elements/components/forms/RatingFormFields.vue'

export default {
  name: 'RatingElementForm',
  components: {
    InjectedFormulaInput,
    FormGroup,
    RatingFormFields,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: {},
      },
      allowedValues: ['value'],
    }
  },
}
</script>
