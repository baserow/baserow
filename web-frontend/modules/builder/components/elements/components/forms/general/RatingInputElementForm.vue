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
    <TextFormatSelector
      v-model="values.label_format"
      :label="$t('textFormatSelector.labelFormat')"
    />

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
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import TextFormatSelector from '@baserow/modules/builder/components/elements/components/forms/TextFormatSelector'

export default {
  name: 'RatingInputElementForm',
  components: {
    InjectedFormulaInput,
    Checkbox,
    RatingFormFields,
    TextFormatSelector,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: {},
        required: false,
        label: {},
        label_format: TEXT_FORMAT_TYPES.PLAIN,
      },
      allowedValues: ['value', 'required', 'label', 'label_format'],
    }
  },
}
</script>
