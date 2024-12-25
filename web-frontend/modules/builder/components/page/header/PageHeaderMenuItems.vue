<template>
  <ul class="header__filter">
    <li
      v-for="itemType in pageHeaderItemTypes"
      :key="itemType.getType()"
      class="header__filter-item"
    >
      <a
        :ref="`button_${itemType.type}`"
        :data-item-type="itemType.type"
        class="header__filter-link"
        @click="
          itemType.onClick(
            $refs[`component_${itemType.type}`][0],
            $refs[`button_${itemType.type}`][0]
          )
        "
      >
        <i class="header__filter-icon" :class="itemType.icon"></i>
        <span class="header__filter-name">{{ itemType.label }}</span>
      </a>
      <component
        :is="itemType.component"
        :ref="`component_${itemType.type}`"
        :data-item-type="itemType.type"
        :page="currentPage"
      />
    </li>
  </ul>
</template>

<script>
export default {
  name: 'PageHeaderMenuItems',
  inject: ['currentPage'],
  computed: {
    pageHeaderItemTypes() {
      return this.$registry.getOrderedList('pageHeaderItem')
    },
  },
}
</script>
