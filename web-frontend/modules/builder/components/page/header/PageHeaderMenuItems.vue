<template>
  <ul class="header__filter">
    <li
      v-for="itemType in pageHeaderItemTypes"
      :key="itemType.getType()"
      class="header__filter-item"
      :data-highlight="`builder-${itemType.type}`"
    >
      <a
        :ref="`button_${itemType.type}`"
        :data-item-type="itemType.type"
        class="header__filter-link"
        :class="{
          'active active--error': itemType.isInError({
            builder,
            page: currentPage,
          }),
        }"
        @click="
          itemType.onClick(
            $refs[`component_${itemType.type}`][0],
            $refs[`button_${itemType.type}`][0]
          )
        "
      >
        <i class="header__filter-icon" :class="itemType.icon"></i>
        <span class="header__filter-name">{{ itemType.label }}</span>
        <i
          v-if="itemType.isInError({ builder, page: currentPage })"
          class="header__filter-error-icon iconoir-warning-circle"
        ></i>
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
  inject: ['currentPage', 'builder'],
  computed: {
    pageHeaderItemTypes() {
      return this.$registry.getOrderedList('pageHeaderItem')
    },
  },
}
</script>
