<template>
  <tr
    v-for="index in count"
    :key="`skeleton-row-${index}`"
    class="data-table__table-row"
    aria-hidden="true"
  >
    <td class="data-table__table-cell" :colspan="columns.length">
      <div class="data-table__table-cell-content skeleton">
        <SkeletonBlock width="200px"></SkeletonBlock>
      </div>
    </td>
  </tr>
</template>

<script>
/**
 * The rows of the CrudTable while the service is fetching them. One placeholder
 * spans the full row instead of one per cell, which keeps the loading state
 * calm, and it renders the real row structure, so the body doesn't resize when
 * the rows arrive.
 */
export default {
  name: 'CrudTableSkeletonRows',
  props: {
    columns: {
      required: true,
      type: Array,
    },
    count: {
      required: false,
      type: Number,
      default: 10,
    },
  },
}
</script>
