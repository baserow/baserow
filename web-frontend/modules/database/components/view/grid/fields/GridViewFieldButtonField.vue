<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-button">
      <!-- A disabled button fires no mouse events, so the tooltip sits on a
           wrapper. -->
      <span
        v-if="requiresReconfiguration"
        v-tooltip="$t('buttonField.requiresReconfiguration')"
      >
        <Button
          size="tiny"
          type="secondary"
          icon="iconoir-warning-triangle"
          disabled
        >
          {{ field.label }}
        </Button>
      </span>
      <Button
        v-else-if="hasWorkflowActions"
        size="tiny"
        type="secondary"
        :loading="dispatching"
        @click="dispatchWorkflowActions"
      >
        {{ field.label }}
      </Button>
      <Button v-else size="tiny" type="secondary" disabled>
        {{ field.label }}
      </Button>
    </div>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'GridViewFieldButtonField',
  mixins: [gridField, buttonField],
}
</script>
