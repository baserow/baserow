<template>
  <div class="card-many-to-many__list-wrapper">
    <div class="card-many-to-many__list">
      <div
        v-for="item in value"
        :key="item.id"
        class="card-many-to-many__item card-multiple-select-option"
        :class="'background-color--' + item.color"
      >
        <span class="card-many-to-many__name">{{ item.value }}</span>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'RowCardFieldMultipleSelect',
  height: 22,
  props: {
    value: {
      type: Array,
      default: () => [],
    },
  },
}
</script>
