<template>
  <div class="long-text-field" :title="row[column.key]">
    {{ row[column.key] }}
  </div>
</template>

<script>
export default {
  name: 'LongTextField',
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
