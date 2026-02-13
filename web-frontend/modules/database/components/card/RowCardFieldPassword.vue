<template>
  <div class="card-text">
    {{ value ? '••••••••••' : '' }}
  </div>
</template>

<script>
export default {
  name: 'RowCardFieldPassword',
  height: 16,
  props: {
    value: {
      type: null,
      default: '',
    },
  },
}
</script>
