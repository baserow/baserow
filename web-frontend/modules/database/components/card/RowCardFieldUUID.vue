<template>
  <div class="card-text">
    {{ value }}
  </div>
</template>

<script>
export default {
  name: 'RowCardFieldUUID',
  height: 16,
  props: {
    value: {
      type: String,
      default: '',
    },
  },
}
</script>
