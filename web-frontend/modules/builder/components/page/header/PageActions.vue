<template>
  <ul class="header__filter">
    <template v-for="actionType in pageActionTypes">
      <li
        v-if="actionType.isActive({ page: currentPage, workspace })"
        :key="actionType.getType()"
        class="header__filter-item header__filter-item--right"
      >
        <a
          :ref="`button_${actionType.type}`"
          class="header__filter-link"
          @click="
            actionType.onClick({
              component: $refs[`component_${actionType.type}`][0],
              button: $refs[`button_${actionType.type}`][0],
              builder: builder,
              page: currentPage,
            })
          "
        >
          <i
            v-if="actionType.icon"
            class="header__filter-icon"
            :class="actionType.icon"
          ></i>
          <span class="header__filter-name">{{ actionType.label }}</span>
        </a>
        <component
          :is="actionType.component"
          :ref="`component_${actionType.type}`"
          :builder="builder"
          :page="currentPage"
        />
      </li>
    </template>
  </ul>
</template>

<script>
export default {
  name: 'PageActions',
  inject: ['workspace', 'builder', 'currentPage'],
  computed: {
    pageActionTypes() {
      return Object.values(this.$registry.getOrderedList('pageAction'))
    },
  },
}
</script>
