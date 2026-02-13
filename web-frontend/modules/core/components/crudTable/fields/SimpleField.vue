<template>
  <div :title="row[column.key]">
    {{ row[column.key] }}
  </div>
</template>

<script>
export default {
  name: 'SimpleField',
  props: {
    row: {
      required: true,
      type: Object,
    },
    column: {
      required: true,
      type: Object,
    },
  },
}
</script>
