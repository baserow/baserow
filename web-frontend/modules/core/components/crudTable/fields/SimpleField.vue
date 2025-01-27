<template functional>
  <div
    :class="[data.staticClass, data.class]"
    :title="props.row[props.column.key]"
    v-on="listeners"
  >
    {{ props.row[props.column.key] }}
  </div>
</template>

<script>
export default {
  name: 'SimpleField',
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
