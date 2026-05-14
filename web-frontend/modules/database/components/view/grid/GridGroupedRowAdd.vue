<template>
  <div
    class="grid-view__row grid-grouped-add-row"
    :style="{
      top: item.y + 'px',
      height: item.height + 'px',
      width: totalWidth + 'px',
    }"
    :data-path="pathSerialised"
    @click="$emit('add-row', item.path)"
  >
    <div
      class="grid-view__column grid-view__column--no-border-right grid-grouped-add-row__cell"
      :style="{ width: idLaneWidth + 'px' }"
    >
      <i class="iconoir-plus" />
    </div>
  </div>
</template>

<script>
/**
 * "+ Add row" affordance rendered at the bottom of every visible
 * leaf group section. Clicking it asks the container to create a
 * new row pre-filled with the group's path values (for fields the
 * user can write to).
 */
export default {
  name: 'GridGroupedRowAdd',
  props: {
    item: {
      type: Object,
      required: true,
      validator: (it) => it.type === 'addRow',
    },
    totalWidth: {
      type: Number,
      default: 0,
    },
    idLaneWidth: {
      type: Number,
      default: 72,
    },
  },
  emits: ['add-row'],
  computed: {
    pathSerialised() {
      return JSON.stringify(this.item.path)
    },
  },
}
</script>

<style lang="scss" scoped>
.grid-grouped-add-row {
  // `.grid-view__row` from the legacy stylesheet sets
  // `position: relative`, which makes the inline `top` ignored as an
  // absolute position. The banner + row components override it with
  // `position: absolute` in their scoped styles — we do the same here
  // so the trailer lands at the y the layout assigned it.
  position: absolute;
  left: 0;
  cursor: pointer;
  background: #ffffff;
  color: #9ca3af;
  display: flex;
  align-items: stretch;
  // Match the right + bottom edges of a data row. Data rows draw
  // a right border per cell and a bottom border on the row; the
  // add-row trailer only has the id-lane cell so it inherits
  // neither without these explicit edges.
  border-right: 1px solid #f0f0f0;
  border-bottom: 1px solid #f0f0f0;

  &:hover {
    background: #f9fafb;
    color: #374151;
  }
}

.grid-grouped-add-row__cell {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  padding: 0 12px;
  font-size: 14px;
}
</style>
