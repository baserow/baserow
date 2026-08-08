<template>
  <div class="control__elements">
    <span
      v-if="hasWorkflowActions"
      v-tooltip="
        rowIsCreated ? null : $t('rowEditFieldButtonField.createRowBefore')
      "
    >
      <!-- The row create modal renders every field before the row exists. -->
      <Button
        size="tiny"
        type="secondary"
        :loading="dispatching"
        :disabled="!rowIsCreated"
        @click="dispatchWorkflowActions"
      >
        {{ field.label }}
      </Button>
    </span>
    <Button v-else size="tiny" type="secondary" disabled>
      {{ field.label }}
    </Button>
  </div>
</template>

<script>
import rowEditField from '@baserow/modules/database/mixins/rowEditField'
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'RowEditFieldButtonField',
  mixins: [rowEditField, buttonField],
}
</script>
