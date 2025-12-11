<template>
  <div class="long-text-field" :title="row[column.key]" v-on="$attrs">
    {{ row[column.key] }}
  </div>
</template>

<script>
export default {
  name: 'LongTextField',
  functional: true,
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
