<template>
  <ABFormGroup
    :error-message="displayFormDataError ? $t('error.requiredField') : ''"
    :style="getStyleOverride('input')"
  >
    <ABCheckbox
      v-model="inputValue"
      :required="element.required"
      :read-only="isEditMode"
    >
      <FormattedText
        :content="resolvedLabel"
        :format="element.label_format"
        preset="inlineLinks"
      />
      <span
        v-if="element.label && element.required"
        :title="$t('error.requiredField')"
        >*</span
      >
    </ABCheckbox>
  </ABFormGroup>
</template>

<script>
import formElement from '@baserow/modules/builder/mixins/formElement'
import FormattedText from '@baserow/modules/builder/components/FormattedText'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'CheckboxElement',
  components: { FormattedText },
  mixins: [formElement],
  computed: {
    resolvedLabel() {
      return ensureString(this.resolveFormula(this.element.label))
    },
  },
}
</script>
