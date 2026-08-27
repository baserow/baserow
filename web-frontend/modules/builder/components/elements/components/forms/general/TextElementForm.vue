<template>
  <form @submit.prevent @keydown.enter.prevent>
    <TextFormatSelector v-model="values.format" />

    <CustomStyleButton
      v-model="values.styles"
      style-key="typography"
      :config-block-types="['typography']"
      :theme="builder.theme"
      :extra-args="{ onlyBody: values.format === TEXT_FORMAT_TYPES.PLAIN }"
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
      />
    </FormGroup>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import CustomStyleButton from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyleButton'
import TextFormatSelector from '@baserow/modules/builder/components/elements/components/forms/TextFormatSelector'

export default {
  name: 'TextElementForm',
  components: {
    InjectedFormulaInput,
    CustomStyleButton,
    TextFormatSelector,
  },
  mixins: [elementForm],
  data() {
    return {
      allowedValues: ['value', 'format', 'styles'],
      values: {
        value: {},
        format: TEXT_FORMAT_TYPES.PLAIN,
        styles: {},
      },
    }
  },
  computed: {
    TEXT_FORMAT_TYPES() {
      return TEXT_FORMAT_TYPES
    },
  },
}
</script>
