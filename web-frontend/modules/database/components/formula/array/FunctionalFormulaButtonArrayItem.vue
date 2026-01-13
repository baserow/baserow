<template>
  <div class="array-field__button">
    <Button
      v-if="isValid(value)"
      tag="a"
      size="tiny"
      type="secondary"
      class="forced-pointer-events-auto array-field__button-button"
      :href="value && value.url"
      target="_blank"
      rel="nofollow noopener noreferrer"
      @mousedown.stop
    >
      <span class=".array-field__ellipsis">{{ getLabelOrURL(value) }}</span>
    </Button>
    <Button v-else size="tiny" type="secondary" tag="a" disabled>
      {{ getLabelOrURL(value) }}
    </Button>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
export default {
  name: 'FunctionalFormulaButtonArrayItem',
  mixins: [linkURLField],
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
}
</script>
