<template>
  <div class="card-text">
    <a
      :href="value"
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
  name: 'RowCardFieldURL',
  height: 16,
  props: {
    value: {
      type: String,
      default: '',
    },
  },
}
</script>
