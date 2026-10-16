<template>
  <div class="data-table__more-wrapper">
    <button
      type="button"
      class="data-table__more"
      :aria-label="$t('crudTable.rowActions')"
      aria-haspopup="menu"
      @click.stop="onClick"
    >
      <i
        class="data-table__more-icon baserow-icon-more-vertical"
        aria-hidden="true"
      ></i>
    </button>
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
