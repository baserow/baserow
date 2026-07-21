<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-button">
      <Button
        v-if="isValid(resolvedButtonValue)"
        tag="a"
        type="secondary"
        size="tiny"
        :href="getHref(resolvedButtonValue)"
        target="_blank"
        rel="nofollow noopener noreferrer"
      >
        {{ getLabelOrURL(resolvedButtonValue) }}
      </Button>
      <Button v-else tag="a" type="secondary" size="tiny" disabled>
        {{ getLabelOrURL(resolvedButtonValue) }}
      </Button>
    </div>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
import buttonField from '@baserow/modules/database/mixins/buttonField'

export default {
  name: 'FunctionalGridViewFieldButtonField',
  mixins: [linkURLField, buttonField],
  props: {
    row: { type: Object, required: true },
    field: { type: Object, required: true },
    value: { type: null, default: null },
  },
}
</script>
