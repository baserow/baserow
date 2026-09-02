<template>
  <span class="search-highlight">
    <template v-for="(segment, index) in segments" :key="index">
      <mark v-if="segment.matched" class="search-highlight__match">{{
        segment.text
      }}</mark>
      <template v-else>{{ segment.text }}</template>
    </template>
  </span>
</template>

<script>
import { splitHighlight } from '@baserow/modules/core/utils/search'

export default {
  name: 'SearchHighlight',
  props: {
    text: {
      type: String,
      required: true,
    },
    query: {
      type: String,
      required: false,
      default: '',
    },
  },
  computed: {
    segments() {
      return splitHighlight(this.text, this.query)
    },
  },
}
</script>
