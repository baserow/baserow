<template>
  <div class="agent-preview-table">
    <table class="agent-preview-table__table">
      <thead>
        <tr class="agent-preview-table__row">
          <th
            v-for="column in table.columns"
            :key="column"
            class="agent-preview-table__cell agent-preview-table__cell--head"
          >
            {{ column }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, index) in table.rows"
          :key="index"
          class="agent-preview-table__row"
        >
          <td
            v-for="(cell, cellIndex) in row"
            :key="cellIndex"
            class="agent-preview-table__cell"
          >
            {{ cell === null || cell === undefined ? '' : cell }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script>
/**
 * The rows a trigger delivered or an approval would write, as a small
 * horizontally scrollable data table.
 */
export default {
  name: 'AgentPreviewTable',
  props: {
    table: {
      type: Object,
      required: true,
    },
  },
}
</script>
