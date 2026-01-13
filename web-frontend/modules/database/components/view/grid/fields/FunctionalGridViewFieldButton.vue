<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-button">
      <Button
        v-if="isValid(value)"
        tag="a"
        type="secondary"
        size="tiny"
        :href="value && value.url"
        target="_blank"
        rel="nofollow noopener noreferrer"
      >
        {{ getLabelOrURL(value) }}
      </Button>
      <Button v-else tag="a" type="secondary" size="tiny" disabled>
        {{ getLabelOrURL(value) }}
      </Button>
    </div>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'

export default {
  name: 'FunctionalGridViewFieldButton',
  mixins: [linkURLField],
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
}
</script>
