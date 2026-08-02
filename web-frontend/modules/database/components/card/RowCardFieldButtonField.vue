<template>
  <div>
    <Button
      v-if="hasWorkflowActions"
      size="tiny"
      type="secondary"
      :loading="dispatching"
      class="forced-pointer-events-auto"
      @mousedown.stop
      @click="dispatchWorkflowActions"
    >
      {{ field.label }}
    </Button>
    <!-- A button with no actions has nothing to run. -->
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
