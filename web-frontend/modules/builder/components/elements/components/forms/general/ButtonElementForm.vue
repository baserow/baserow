<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="button"
      :config-block-types="['button']"
      :theme="builder.theme"
    />
    <FormGroup
      small-label
      :label="$t('buttonElementForm.valueLabel')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.value"
        :placeholder="$t('buttonElementForm.valuePlaceholder')"
      />
    </FormGroup>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import elementForm from '@baserow/modules/builder/mixins/elementForm'

export default {
  name: 'ButtonElementForm',
  components: {
    InjectedFormulaInput,
    CustomStyleButton,
  },
  mixins: [elementForm],
  data() {
    return {
      values: {
        value: {},
        styles: {},
      },
      allowedValues: ['value', 'styles'],
    }
  },
}
</script>
