<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyleButton
      v-model="values.styles"
      style-key="typography"
      :config-block-types="['typography']"
      :theme="builder.theme"
      :extra-args="{ onlyBody: !isMarkdown }"
    />
    <FormGroup
      small-label
      :label="$t('textElementForm.textTitle')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.value"
        :placeholder="$t('textElementForm.textPlaceholder')"
        :allowed-formats="allowedFormats"
      />
    </FormGroup>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import {
  BASEROW_FORMULA_FORMAT_MARKDOWN,
  BASEROW_FORMULA_FORMATS,
} from '@baserow/modules/core/formula/constants'

export default {
  name: 'TextElementForm',
  components: {
    InjectedFormulaInput,
    CustomStyleButton,
  },
  mixins: [elementForm],
  data() {
    return {
      allowedValues: ['value', 'styles'],
      values: {
        value: {},
        styles: {},
      },
      // The format is picked in the formula input and stored on the value.
      allowedFormats: BASEROW_FORMULA_FORMATS,
    }
  },
  computed: {
    isMarkdown() {
      return this.values.value?.format === BASEROW_FORMULA_FORMAT_MARKDOWN
    },
  },
}
</script>
