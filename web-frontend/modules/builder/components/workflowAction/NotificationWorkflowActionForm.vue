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
    <TextFormatSelector
      v-model="values.title_format"
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
    <TextFormatSelector
      v-model="values.description_format"
      :label="$t('notificationWorkflowActionForm.descriptionFormat')"
    />
  </form>
</template>

<script>
import form from '@baserow/modules/core/mixins/form'
import InjectedFormulaInput from '@baserow/modules/core/components/formula/InjectedFormulaInput'
import { TEXT_FORMAT_TYPES } from '@baserow/modules/builder/enums'
import TextFormatSelector from '@baserow/modules/builder/components/elements/components/forms/TextFormatSelector'

export default {
  name: 'NotificationWorkflowActionForm',
  components: { InjectedFormulaInput, TextFormatSelector },
  mixins: [form],
  data() {
    return {
      allowedValues: [
        'title',
        'title_format',
        'description',
        'description_format',
      ],
      values: {
        title: {},
        title_format: TEXT_FORMAT_TYPES.PLAIN,
        description: {},
        description_format: TEXT_FORMAT_TYPES.PLAIN,
      },
    }
  },
}
</script>
