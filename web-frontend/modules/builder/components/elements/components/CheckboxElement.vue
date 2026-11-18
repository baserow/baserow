<template>
  <ABFormGroup
    :error-message="displayFormDataError ? $t('error.requiredField') : ''"
    :style="getStyleOverride('input')"
  >
    <ABCheckbox
      :model-value="inputValue"
      :required="element.required"
      :read-only="isEditMode"
      :disabled="workflowActionsInProgress"
      @update:model-value="onSelectionChange"
    >
      <ABFormattedText
        :value="resolvedLabel"
        :format="element.label?.format"
        profile="inline"
      />
      <span
        v-if="element.label && element.required"
        :title="$t('error.requiredField')"
      >
        *</span
      >
    </ABCheckbox>
  </ABFormGroup>
</template>

<script>
import changeableFormElement from '@baserow/modules/builder/mixins/changeableFormElement'
import { ensureString } from '@baserow/modules/core/utils/validator'

export default {
  name: 'CheckboxElement',
  mixins: [changeableFormElement],
  computed: {
    resolvedLabel() {
      return ensureString(this.resolveFormula(this.element.label))
    },
  },
}
</script>
