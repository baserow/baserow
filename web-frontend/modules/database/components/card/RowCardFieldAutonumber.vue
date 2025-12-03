<template>
  <div class="card-number">
    {{ value }}
  </div>
</template>

<script>
export default {
  name: 'RowCardFieldAutonumber',
  height: 16,
  props: {
    value: {
      type: null,
      default: null,
    },
  },
}
</script>
