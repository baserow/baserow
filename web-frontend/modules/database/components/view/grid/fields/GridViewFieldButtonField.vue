<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-button">
      <Button
        v-if="hasWorkflowActions"
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
