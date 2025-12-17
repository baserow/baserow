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
      />
      <template #after-input>
        <CustomStyleButton
          v-model="values.styles"
          style-key="cell"
          :config-block-types="['table', 'typography']"
          :theme="baseTheme"
          :on-styles-changed="onFieldStylesChanged"
          :extra-args="{ onlyCell: true, onlyBody: true, noAlignment: true }"
          variant="normal"
        />
      </template>
    </FormGroup>
  </form>
</template>

<script>
import collectionFieldForm from '@baserow/modules/builder/mixins/collectionFieldForm'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'

export default {
  name: 'TextField',
  components: { InjectedFormulaInput, CustomStyleButton },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['value', 'styles'],
      values: {
        value: {},
        styles: {},
      },
    }
  },
}
</script>
