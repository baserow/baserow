<template>
  <tbody class="data-table__row-group">
    <tr
      class="data-table__table-row"
      :class="{
        'data-table__table-row--expandable': expandable,
        'data-table__table-row--expanded': expanded,
      }"
      @click="onRowClick"
    >
      <td
        v-for="col in columns"
        :key="col.key"
        class="data-table__table-cell"
        :class="{
          'data-table__table-cell--sticky-left': col.stickyLeft,
          'data-table__table-cell--sticky-right': col.stickyRight,
          [`data-table__table-cell--${col.key}`]: true,
        }"
        @contextmenu="$emit('row-context', { col, row, event: $event })"
      >
        <div class="data-table__table-cell-content">
          <component
            :is="col.cellComponent"
            :row="row"
            :column="col"
            v-bind="$attrs"
            @row-context="(payload) => $emit('row-context', payload)"
            @row-update="$emit('row-update', $event)"
            @row-delete="$emit('row-delete', $event)"
            @refresh="$emit('refresh')"
          />
          <button
            v-if="expandable && col.key === (expandColumnKey || columns[0].key)"
            type="button"
            class="data-table__expand"
            :aria-label="
              $t(expanded ? 'crudTable.collapseRow' : 'crudTable.expandRow')
            "
            :aria-expanded="expanded"
            :aria-controls="expanded ? expandedId : undefined"
            @click.stop="$emit('toggle')"
          >
            <slot name="row-expansion-toggle" :row="row" :expanded="expanded" />
            <i
              :class="
                expanded ? 'iconoir-nav-arrow-up' : 'iconoir-nav-arrow-down'
              "
              aria-hidden="true"
            />
          </button>
        </div>
      </td>
    </tr>
  </tbody>
  <tbody v-if="expanded" :id="expandedId" class="data-table__expanded-rows">
    <slot name="expanded-row" :row="row" :columns="columns" />
  </tbody>
</template>

<script setup>
import { useId } from 'vue'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  row: { type: Object, required: true },
  columns: { type: Array, required: true },
  expandable: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
  expandColumnKey: { type: String, default: null },
})
const emit = defineEmits([
  'row-context',
  'row-update',
  'row-delete',
  'refresh',
  'toggle',
])
const expandedId = useId()

function onRowClick(event) {
  if (!props.expandable || event.defaultPrevented) return

  // Cell components own their interactions. Custom click targets can opt out
  // with data-prevent-row-toggle even when they aren't native controls.
  const control = event.target.closest(
    'a, button, input, select, textarea, label, summary, [tabindex], ' +
      '[role="button"], [role="link"], [role="checkbox"], [role="combobox"], ' +
      '[role="menuitem"], [contenteditable]:not([contenteditable="false"]), ' +
      '[data-prevent-row-toggle]'
  )
  if (control && event.currentTarget.contains(control)) return

  const selection = window.getSelection()
  if (
    selection &&
    !selection.isCollapsed &&
    event.currentTarget.contains(selection.anchorNode)
  )
    return

  emit('toggle')
}
</script>
