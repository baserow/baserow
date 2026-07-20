<template>
  <div>
    <i
      v-if="row[column.key]"
      :class="column.additionalProps.icon"
      :title="column.additionalProps.title"
    ></i>
    <span v-else>-</span>
  </div>
</template>

<script>
export default {
  name: 'BooleanIconField',
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
