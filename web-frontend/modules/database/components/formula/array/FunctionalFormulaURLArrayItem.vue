<template>
  <div v-if="value" class="array-field__item">
    <div class="array-field__ellipsis" :title="value">
      <a
        v-if="selected"
        :href="getHref(value)"
        target="_blank"
        rel="nofollow noopener noreferrer"
        class="forced-pointer-events-auto"
        @mousedown.stop
        >{{ value }}</a
      >
      <u v-else>{{ value }}</u>
    </div>
  </div>
</template>

<script>
import linkURLField from '@baserow/modules/database/mixins/linkURLField'
export default {
  name: 'FunctionalFormulaURLArrayItem',
  mixins: [linkURLField],
  props: {
    value: {
      type: String,
      default: '',
    },
    selected: {
      type: Boolean,
      default: false,
    },
  },
}
</script>
