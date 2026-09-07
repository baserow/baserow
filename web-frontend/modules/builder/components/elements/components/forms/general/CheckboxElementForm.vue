<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="input"
      :config-block-types="['input']"
      :theme="builder.theme"
      :extra-args="{ onlyInput: true }"
    />
    <FormGroup
      small-label
      :label="$t('checkboxElementForm.labelTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.label"
        :placeholder="$t('generalForm.labelPlaceholder')"
      />
    </FormGroup>
    <FormulaFormatSelector
      v-model="values.label"
      :label="$t('textFormatSelector.labelFormat')"
    />

    <FormGroup
      small-label
      :label="$t('checkboxElementForm.valueTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.default_value"
        :placeholder="$t('generalForm.valuePlaceholder')"
      />
    </FormGroup>
    <FormGroup
      small-label
      required
      :label="$t('checkboxElementForm.requiredTitle')"
    >
      <Checkbox v-model="values.required"></Checkbox>
    </FormGroup>
  </form>
</template>

<script>
import formElementForm from '@baserow/modules/builder/mixins/formElementForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import FormulaFormatSelector from '@baserow/modules/builder/components/elements/components/forms/FormulaFormatSelector'

export default {
  name: 'CheckboxElementForm',
  components: { InjectedFormulaInput, CustomStyleButton, FormulaFormatSelector },
  mixins: [formElementForm],
  data() {
    return {
      allowedValues: [
        'label',
        'default_value',
        'required',
        'styles',
      ],
      values: {
        label: {},
        default_value: {},
        required: false,
        styles: {},
      },
    }
  },
}
</script>
