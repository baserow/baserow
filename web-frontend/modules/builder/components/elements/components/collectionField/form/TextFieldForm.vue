<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('textFieldForm.fieldValueLabel')"
      class="margin-bottom-2"
      horizontal
      required
    >
      <InjectedFormulaInput
        v-model="values.value"
        :placeholder="$t('textFieldForm.fieldValuePlaceholder')"
        :allowed-formats="allowedFormats"
      />
    </FormGroup>
  </form>
</template>

<script>
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import { BASEROW_FORMULA_FORMATS } from '@baserow/modules/core/formula/constants'

export default {
  name: 'TextField',
  components: { InjectedFormulaInput },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['value', 'styles'],
      values: {
        value: {},
        styles: {},
      },
      allowedFormats: BASEROW_FORMULA_FORMATS,
    }
  },
}
</script>
