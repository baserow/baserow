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
      v-else-if="canClick"
      size="tiny"
      type="secondary"
      :loading="dispatching"
      class="forced-pointer-events-auto"
      @mousedown.stop
      @click="dispatchWorkflowActions"
    >
      {{ field.label }}
    </Button>
    <!-- A card takes the pointer away from everything inside it, so the
         wrapper asks for it back while it has a reason to show. -->
    <span
      v-else
      v-tooltip="disabledReason"
      :class="{ 'forced-pointer-events-auto': disabledReason }"
    >
      <Button size="tiny" type="secondary" disabled>
        {{ field.label }}
      </Button>
    </span>
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
    workspaceId: { type: Number, required: false, default: null },
  },
  height: 26,
}
</script>
