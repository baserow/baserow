<template>
  <ul class="context__menu">
    <li v-if="canSelectRow" class="context__menu-item">
      <a
        class="context__menu-item-link"
        @click="onItemClick($event, 'select-row', row)"
      >
        <i class="context__menu-item-icon iconoir-check-circle"></i>
        {{ $t('gridView.selectRow') }}
      </a>
    </li>
    <li v-if="canCreateRow" class="context__menu-item">
      <a
        class="context__menu-item-link"
        @click="onItemClick($event, 'insert-above', row)"
      >
        <i class="context__menu-item-icon iconoir-arrow-up"></i>
        {{ $t('gridView.insertRowAbove') }}
      </a>
    </li>
    <li v-if="canCreateRow" class="context__menu-item">
      <a
        class="context__menu-item-link"
        @click="onItemClick($event, 'insert-below', row)"
      >
        <i class="context__menu-item-icon iconoir-arrow-down"></i>
        {{ $t('gridView.insertRowBelow') }}
      </a>
    </li>
    <li v-if="canCreateRow" class="context__menu-item">
      <a
        class="context__menu-item-link"
        @click="onItemClick($event, 'duplicate-row', row)"
      >
        <i class="context__menu-item-icon iconoir-copy"></i>
        {{ $t('gridView.duplicateRow') }}
      </a>
    </li>
    <li v-if="!readOnly" class="context__menu-item">
      <a
        class="context__menu-item-link"
        @click="onItemClick($event, 'copy-row-url', row)"
      >
        <i class="context__menu-item-icon iconoir-link"></i>
        {{ $t('gridView.copyRowURL') }}
      </a>
    </li>
    <li v-if="row !== null && !row._.loading" class="context__menu-item">
      <a
        class="context__menu-item-link"
        @click="onItemClick($event, 'open-row-modal', row)"
      >
        <i class="context__menu-item-icon iconoir-expand"></i>
        {{ $t('gridView.enlargeRow') }}
      </a>
    </li>
    <li
      v-if="canDeleteRow"
      class="context__menu-item context__menu-item--with-separator"
    >
      <a
        class="context__menu-item-link"
        @click="onItemClick($event, 'delete-row', row)"
      >
        <i class="context__menu-item-icon iconoir-bin"></i>
        {{ $t('gridView.deleteRow') }}
      </a>
    </li>
  </ul>
</template>

<script>
/**
 * Single-row context menu items for grid views. Stateless: emits a typed event
 * per action; the parent component owns the wiring to its store and the
 * Context wrapper that positions the menu next to the mouse.
 *
 * `canCreateRow`, `canDeleteRow`, `canSelectRow` are computed by the
 * caller because they are permission/two-way-sync checks tied to the table,
 * view, and workspace. This keeps the component presentational and the checks
 * near the state they depend on.
 */
export default {
  name: 'GridRowContextItems',
  props: {
    row: {
      type: Object,
      default: null,
    },
    readOnly: {
      type: Boolean,
      default: false,
    },
    canCreateRow: {
      type: Boolean,
      default: false,
    },
    canDeleteRow: {
      type: Boolean,
      default: false,
    },
    canSelectRow: {
      type: Boolean,
      default: true,
    },
  },
  emits: [
    'select-row',
    'insert-above',
    'insert-below',
    'duplicate-row',
    'copy-row-url',
    'open-row-modal',
    'delete-row',
  ],
  methods: {
    onItemClick(event, name, row) {
      // The `gridField` mixin uses this flag to keep an open editor from closing when
      // the user clicks a menu item.
      event.preventFieldCellUnselect = true
      this.$emit(name, row)
    },
  },
}
</script>
