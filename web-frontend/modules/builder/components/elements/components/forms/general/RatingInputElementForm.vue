<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('generalForm.labelTitle')"
      required
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.label"
        :placeholder="$t('generalForm.labelPlaceholder')"
      />
    </FormGroup>

    <FormGroup
      :label="$t('generalForm.requiredTitle')"
      class="margin-bottom-2"
      required
      small-label
    >
      <Checkbox v-model="values.required" />
    </FormGroup>

    <FormGroup
      small-label
      required
      :label="$t('generalForm.defaultValueTitle')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.value"
        data-test-id="rating-form-value"
        :placeholder="$t('generalForm.defaultValuePlaceholder')"
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
import Checkbox from '@baserow/modules/core/components/Checkbox'
import RatingFormFields from '@baserow/modules/builder/components/elements/components/forms/RatingFormFields.vue'

export default {
  name: 'RatingInputElementForm',
  components: {
    InjectedFormulaInput,
    Checkbox,
    RatingFormFields,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: {},
        required: false,
        label: {},
      },
      allowedValues: ['value', 'required', 'label'],
    }
  },
}
</script>
