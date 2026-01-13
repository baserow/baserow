<template>
  <div class="card-text">
    <a
      v-if="isValid(value)"
      :href="value && value.url"
      target="_blank"
      rel="nofollow noopener noreferrer"
      class="forced-pointer-events-auto"
      @mousedown.stop
    >
      {{ getLabelOrURL(value) }}
    </a>
    <template v-else>
      {{ getLabelOrURL(value) }}
    </template>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
export default {
  name: 'RowCardFieldLink',
  mixins: [linkURLField],
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
  height: 16,
}
</script>
