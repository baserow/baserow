<template>
  <div>
    <Button
      v-if="isValid(value)"
      :href="value && value.url"
      tag="a"
      target="_blank"
      rel="nofollow noopener noreferrer"
      size="tiny"
      type="secondary"
      class="forced-pointer-events-auto"
      @mousedown.stop
    >
      {{ getLabelOrURL(value) }}
    </Button>
    <Button v-else tag="a" type="secondary" size="tiny" disabled>
      {{ getLabelOrURL(value) }}
    </Button>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
export default {
  name: 'RowCardFieldButton',
  mixins: [linkURLField],
  props: {
    value: {
      type: Object,
      default: null,
    },
  },
  height: 26,
}
</script>
