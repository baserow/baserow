<template>
  <div ref="cell" class="grid-view__cell">
    <div class="grid-field-text">
      <a
        v-if="selected && isValid(value)"
        :href="value && value.url"
        target="_blank"
        rel="nofollow noopener noreferrer"
      >
        {{ getLabelOrURL(value) }}
      </a>
      <u v-else-if="isValid(value)">
        {{ getLabelOrURL(value) }}
      </u>
      <span v-else>
        {{ getLabelOrURL(value) }}
      </span>
    </div>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'

export default {
  name: 'FunctionalGridViewFieldLinkURL',
  mixins: [linkURLField],
  props: {
    value: {
      type: Object,
      default: null,
    },
    selected: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
