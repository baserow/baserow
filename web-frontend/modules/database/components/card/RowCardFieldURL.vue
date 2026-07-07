<template>
  <div class="card-text">
    <a
      :href="getHref(value)"
      target="_blank"
      rel="nofollow noopener noreferrer"
      class="forced-pointer-events-auto"
      @mousedown.stop
      >{{ value }}</a
    >
  </div>
</template>

<script>
import { ensureUrlProtocol } from '@baserow/modules/core/utils/url'

export default {
  name: 'RowCardFieldURL',
  height: 16,
  props: {
    value: {
      type: String,
      default: '',
    },
  },
  methods: {
    getHref(value) {
      return value ? ensureUrlProtocol(value) : undefined
    },
  },
}
</script>
