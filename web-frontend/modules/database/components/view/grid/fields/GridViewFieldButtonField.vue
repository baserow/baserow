<template>
  <div ref="cell" class="grid-view__cell active">
    <!-- A disabled button fires no mouse events, so the tooltip sits on the
         wrapper. -->
    <div
      v-tooltip="
        requiresReconfiguration
          ? $t('buttonField.requiresReconfiguration')
          : null
      "
      class="grid-field-button"
    >
      <Button
        v-if="requiresReconfiguration"
        size="tiny"
        type="secondary"
        icon="iconoir-warning-triangle"
        disabled
      >
        {{ field.label }}
      </Button>
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
