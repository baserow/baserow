<template>
  <div class="grid-view__group-value-many-to-many">
    <div
      v-for="item in value"
      :key="item.id"
      class="grid-view__group-value-select-option"
      :class="'background-color--' + item.color"
    >
      <div class="grid-view__group-value-select-option-name">
        {{ item.value }}
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'GridViewGroupValueMultipleSelect',
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
