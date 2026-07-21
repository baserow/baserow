<template>
  <div>
    <Button
      v-if="isValid(resolvedButtonValue)"
      :href="getHref(resolvedButtonValue)"
      tag="a"
      target="_blank"
      rel="nofollow noopener noreferrer"
      size="tiny"
      type="secondary"
      class="forced-pointer-events-auto"
      @mousedown.stop
    >
      {{ getLabelOrURL(resolvedButtonValue) }}
    </Button>
    <Button v-else tag="a" type="secondary" size="tiny" disabled>
      {{ getLabelOrURL(resolvedButtonValue) }}
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
