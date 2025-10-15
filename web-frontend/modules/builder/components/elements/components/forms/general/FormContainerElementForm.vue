<template>
  <form @submit.prevent @keydown.enter.prevent>
    <CustomStyle
      v-model="values.styles"
      style-key="button"
      :config-block-types="['button']"
      :theme="builder.theme"
    />
    <FormGroup
      small-label
      :label="$t('formContainerElementForm.submitButtonLabel')"
      class="margin-bottom-2"
      required
    >
      <InjectedFormulaInput
        v-model="values.submit_button_label"
        :placeholder="$t('formContainerElementForm.submitButtonPlaceholder')"
      />
    </FormGroup>
    <FormGroup
      :label="$t('formContainerElementForm.resetToInitialValuesTitle')"
      :helper-text="
        $t('formContainerElementForm.resetToInitialValuesDescription')
      "
      small-label
      required
    >
      <Checkbox
        v-model="values.reset_initial_values_post_submission"
      ></Checkbox>
    </FormGroup>
  </form>
</template>

<script>
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput.vue'
import elementForm from '@baserow/modules/builder/mixins/elementForm'
import CustomStyle from '@baserow/modules/builder/components/elements/components/forms/style/CustomStyle'

export default {
  name: 'FormContainerElementForm',
  components: { InjectedFormulaInput, CustomStyle },
  mixins: [elementForm],
  data() {
    return {
      values: {
        submit_button_label: {},
        reset_initial_values_post_submission: false,
        styles: {},
      },
      allowedValues: [
        'submit_button_label',
        'reset_initial_values_post_submission',
        'styles',
      ],
    }
  },
}
</script>
