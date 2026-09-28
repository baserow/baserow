<template>
  <form @submit.prevent="submit">
    <FormGroup
      small-label
      :label="$t('notificationWorkflowActionForm.titleLabel')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.title"
        :placeholder="$t('notificationWorkflowActionForm.titlePlaceholder')"
        :allowed-formats="allowedFormats"
      />
    </FormGroup>
    <FormGroup
      small-label
      :label="$t('notificationWorkflowActionForm.descriptionLabel')"
      class="margin-bottom-2"
    >
      <InjectedFormulaInput
        v-model="values.description"
        :placeholder="
          $t('notificationWorkflowActionForm.descriptionPlaceholder')
        "
        :allowed-formats="allowedFormats"
      />
    </FormGroup>
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import { BASEROW_FORMULA_FORMATS } from '@baserow/modules/core/formula/constants'

export default {
  name: 'NotificationWorkflowActionForm',
  components: { InjectedFormulaInput },
  mixins: [form],
  data() {
    return {
      values: {
        title: {},
        description: {},
      },
      allowedFormats: BASEROW_FORMULA_FORMATS,
    }
  },
}
</script>
