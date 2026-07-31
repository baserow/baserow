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
      <Button
        v-else-if="isValid(resolvedButtonValue)"
        tag="a"
        size="tiny"
        type="secondary"
        rel="nofollow noopener noreferrer"
        :href="getHref(resolvedButtonValue)"
        target="_blank"
      >
        {{ resolvedButtonValue.label }}
      </Button>
      <Button v-else type="secondary" tag="a" size="tiny" disabled>
        {{ resolvedButtonValue.label }}
      </Button>
    </div>
  </div>
</template>

<script>
import gridField from '@baserow/modules/database/mixins/gridField'
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'GridViewFieldButtonField',
  mixins: [gridField, linkURLField, buttonField],
}
</script>
