<template>
  <form @submit.prevent @keydown.enter.prevent>
    <FormGroup
      small-label
      :label="$t('textFieldForm.fieldFormatLabel')"
      class="margin-bottom-2"
      horizontal
      required
    >
      <RadioGroup
        v-model="values.format"
        type="button"
        :options="textFormatTypeOptions"
      >
      </RadioGroup>
    </FormGroup>
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
          :extra-args="{
            onlyCell: true,
            onlyBody: values.format === TEXT_FORMAT_TYPES.PLAIN,
            noAlignment: true,
          }"
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
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'

export default {
  name: 'TextField',
  components: { InjectedFormulaInput, CustomStyleButton },
  mixins: [collectionFieldForm],
  data() {
    return {
      allowedValues: ['value', 'format', 'styles'],
      values: {
        value: {},
        format: TEXT_FORMAT_TYPES.PLAIN,
        styles: {},
      },
      textFormatTypeOptions: [
        {
          value: TEXT_FORMAT_TYPES.PLAIN,
          label: this.$t('textFieldForm.fieldFormatPlain'),
        },
        {
          value: TEXT_FORMAT_TYPES.MARKDOWN,
          label: this.$t('textFieldForm.fieldFormatMarkdown'),
        },
      ],
    }
  },
  computed: {
    TEXT_FORMAT_TYPES() {
      return TEXT_FORMAT_TYPES
    },
  },
}
</script>
