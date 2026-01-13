<template>
  <div class="data-table__more-wrapper">
    <a class="data-table__more" @click.prevent="onClick">
      <i class="data-table__more-icon baserow-icon-more-horizontal"></i>
    </a>
  </div>
</template>

<script>
export default {
  name: 'MoreField',
  props: {
    row: {
      required: true,
      type: Object,
    },
  },
  emits: ['row-context'],
  methods: {
    onClick(event) {
      this.$emit('row-context', {
        row: this.row,
        event,
        target: event.currentTarget,
        time: Date.now(),
      })
    },
  },
}
</script>
