<template>
  <ul class="context__menu">
    <li class="context__menu-item">
      <a class="context__menu-item-link" @click="onClick($event, 'copy-cells')">
        <i class="context__menu-item-icon iconoir-copy"></i>
        {{ $t('gridView.copyCells') }}
      </a>
    </li>
    <li class="context__menu-item">
      <a
        class="context__menu-item-link"
        @click="onClick($event, 'copy-cells-with-header')"
      >
        <i class="context__menu-item-icon iconoir-copy"></i>
        {{ $t('gridView.copyCellsWithHeader') }}
      </a>
    </li>
    <li v-if="canDeleteRows" class="context__menu-item">
      <a
        class="context__menu-item-link"
        :class="{ 'context__menu-item-link--loading': loading }"
        @click="onClick($event, 'delete-rows')"
      >
        <i class="context__menu-item-icon iconoir-bin"></i>
        {{ $t('gridView.deleteRows') }}
      </a>
    </li>
  </ul>
</template>

<script>
/**
 * Multi-row context menu items: actions that apply to N selected
 * rows (checkbox selection or, later, the multi-cell rectangle).
 * Shared between flat and grouped grids — emits typed events the
 * caller wires to its own store. Stateless: permission checks are
 * passed in as props so this component stays presentational.
 *
 * `onClick` wraps every emit to set `preventFieldCellUnselect` on
 * the click event — same flag the single-row menu sets so an open
 * cell editor in the flat grid stays open.
 */
export default {
  name: 'GridMultiRowContextItems',
  props: {
    canDeleteRows: {
      type: Boolean,
      default: false,
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['copy-cells', 'copy-cells-with-header', 'delete-rows'],
  methods: {
    onClick(event, name) {
      event.preventFieldCellUnselect = true
      this.$emit(name)
    },
  },
}
</script>
