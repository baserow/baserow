<template>
  <div class="card-text">
    <a
      :href="'mailto:' + value"
      target="_blank"
      rel="nofollow noopener noreferrer"
      class="forced-pointer-events-auto"
      @mousedown.stop
      >{{ value }}</a
    >
  </div>
</template>

<script>
export default {
  name: 'RowCardFieldEmail',
  height: 16,
  props: {
    value: {
      type: String,
      default: '',
    },
  },
}
</script>
