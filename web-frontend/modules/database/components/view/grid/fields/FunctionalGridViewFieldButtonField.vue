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
          type="secondary"
          size="tiny"
          icon="iconoir-warning-triangle"
          disabled
        >
          {{ field.label }}
        </Button>
      </span>
      <Button
        v-else-if="hasWorkflowActions"
        type="secondary"
        size="tiny"
        :loading="dispatching"
        @click="dispatchWorkflowActions"
      >
        {{ field.label }}
      </Button>
      <Button v-else type="secondary" size="tiny" disabled>
        {{ field.label }}
      </Button>
    </div>
  </div>
</template>

<script>
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'FunctionalGridViewFieldButtonField',
  mixins: [buttonField],
  props: {
    row: { type: Object, required: true },
    field: { type: Object, required: true },
    value: { type: null, default: null },
  },
}
</script>
