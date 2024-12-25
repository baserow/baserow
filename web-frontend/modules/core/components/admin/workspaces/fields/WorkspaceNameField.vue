<template functional>
  <div class="group-admin-name" :class="[data.staticClass, data.class]">
    <div class="group-admin-name__name" :title="props.row[props.column.key]">
      {{ props.row[props.column.key] }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'WorkspaceNameField',
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
