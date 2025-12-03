<template>
  <div ref="cell" class="grid-view__cell grid-field-many-to-many__cell">
    <div class="grid-field-many-to-many__list grid-field-multiple-select__list">
      <div
        v-for="item in value"
        :key="item.id"
        class="grid-field-multiple-select__item"
        :class="'background-color--' + item.color"
      >
        <div v-if="value" class="grid-field-many-to-many__name">
          {{ item.value }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FunctionalGridViewFieldMultipleSelect',
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
