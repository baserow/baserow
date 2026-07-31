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
    <Button
      v-else-if="isValid(resolvedButtonValue)"
      :href="getHref(resolvedButtonValue)"
      tag="a"
      target="_blank"
      rel="nofollow noopener noreferrer"
      size="tiny"
      type="secondary"
      class="forced-pointer-events-auto"
      @mousedown.stop
    >
      {{ resolvedButtonValue.label }}
    </Button>
    <Button v-else tag="a" type="secondary" size="tiny" disabled>
      {{ resolvedButtonValue.label }}
    </Button>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'RowCardFieldButtonField',
  mixins: [linkURLField, buttonField],
  props: {
    row: { type: Object, required: true },
    field: { type: Object, required: true },
    value: { type: null, default: null },
  },
  height: 26,
}
</script>
