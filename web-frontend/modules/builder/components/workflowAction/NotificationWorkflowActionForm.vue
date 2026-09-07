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
      />
    </FormGroup>
    <FormulaFormatSelector
      v-model="values.title"
      :label="$t('notificationWorkflowActionForm.titleFormat')"
    />
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
      />
    </FormGroup>
    <FormulaFormatSelector
      v-model="values.description"
      :label="$t('notificationWorkflowActionForm.descriptionFormat')"
    />
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import FormulaFormatSelector from '@baserow/modules/builder/components/elements/components/forms/FormulaFormatSelector'

export default {
  name: 'NotificationWorkflowActionForm',
  components: { InjectedFormulaInput, FormulaFormatSelector },
  mixins: [form],
  data() {
    return {
      allowedValues: ['title', 'description'],
      values: {
        title: {},
        description: {},
      },
    }
  },
}
</script>
