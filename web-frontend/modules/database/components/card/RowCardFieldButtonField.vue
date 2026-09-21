<template>
  <div>
    <!-- A disabled button fires no mouse events, so the tooltip sits on a
         wrapper. -->
    <span
      v-if="requiresReconfiguration"
      v-tooltip="$t('buttonField.requiresReconfiguration')"
      class="forced-pointer-events-auto"
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
      class="forced-pointer-events-auto"
      @mousedown.stop
      @click="dispatchWorkflowActions"
    >
      {{ field.label }}
    </Button>
    <Button v-else size="tiny" type="secondary" disabled>
      {{ field.label }}
    </Button>
  </div>
</template>

<script>
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'RowCardFieldButtonField',
  mixins: [buttonField],
  props: {
    row: { type: Object, required: true },
    field: { type: Object, required: true },
    value: { type: null, default: null },
  },
  height: 26,
}
</script>
