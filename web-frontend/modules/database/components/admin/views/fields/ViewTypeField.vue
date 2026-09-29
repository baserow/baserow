<template>
  <div :title="viewType.getName()">
    <i :class="viewType.iconClass"></i>
    {{ viewType.getName() }}
  </div>
</template>

<script>
export default {
  name: 'ViewTypeField',
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
  computed: {
    viewType() {
      return this.$registry.get('view', this.row.type)
    },
  },
}
</script>
