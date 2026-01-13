<template>
  <div class="array-field__item">
    <div class="array-field__ellipsis">
      <a
        v-if="selected && isValid(value)"
        :href="value && value.url"
        target="_blank"
        rel="nofollow noopener noreferrer"
        class="forced-pointer-events-auto"
        @mousedown.stop
      >
        {{ getLabelOrURL(value) }}
      </a>
      <u v-else-if="isValid(value)">
        {{ getLabelOrURL(value) }}
      </u>
      <template v-else>
        {{ getLabelOrURL(value) }}
      </template>
    </div>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
export default {
  name: 'FunctionalFormulaLinkArrayItem',
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
