<template>
  <div class="group-admin-name">
    <div class="group-admin-name__name" :title="row[column.key]">
      {{ row[column.key] }}
    </div>
  </div>
</template>

<script>
export default {
  name: 'WorkspaceNameField',
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
