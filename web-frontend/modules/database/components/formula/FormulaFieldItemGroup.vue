<template>
  <ul class="formula-field__item-group">
    <li class="formula-field__item-group-title">
      {{ title }}
      {{ getFilterIndicator(unfilteredItems, filteredItems) }}
    </li>
    <li
      v-for="item in filteredItems"
      :key="item.value"
      class="formula-field__item"
    >
      <a
        href="#"
        class="formula-field__item-link"
        @mouseover="$emit('hover-item', item)"
        @mousedown.prevent
        @click.stop="$emit('click-item', item)"
      >
        <i class="formula-field__item-icon" :class="[item.icon]" />
        {{ showOperator && item.operator ? item.operator : item.value }}
      </a>
    </li>
  </ul>
</template>
<script>
export default {
  name: 'FormulaFieldItemGroup',
  props: {
    title: {
      type: String,
      required: true,
    },
    unfilteredItems: {
      type: Array,
      required: true,
    },
    filteredItems: {
      type: Array,
      required: true,
    },
    showOperator: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  emits: ['click-item', 'hover-item'],
  methods: {
    getFilterIndicator(unfilteredList, filteredList) {
      const numFiltered = unfilteredList.length - filteredList.length
      return numFiltered === 0 ? '' : `(${numFiltered} filtered)`
    },
  },
}
</script>
