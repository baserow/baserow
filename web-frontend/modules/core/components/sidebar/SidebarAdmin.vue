<template>
  <div class="sidebar__section sidebar__section--scrollable">
    <div class="sidebar__section-scrollable">
      <div class="sidebar__section-scrollable-inner">
        <ul class="tree">
          <template
            v-for="(category, index) in groupedSortedAdminTypes"
            :key="category.name"
          >
            <li
              v-if="showSectionSeparators && index > 0"
              class="tree__separator"
              aria-hidden="true"
            ></li>
            <li
              class="tree__heading"
              :class="{ 'margin-top-2': index > 0 && !showSectionSeparators }"
            >
              {{ category.name }}
            </li>
            <SidebarAdminItem
              v-for="adminType in category.items"
              :key="adminType.type"
              :admin-type="adminType"
              @activate="$emit('activate')"
            />
          </template>
        </ul>
      </div>
    </div>
  </div>
</template>

<script>
import SidebarAdminItem from '@baserow/modules/core/components/sidebar/SidebarAdminItem.vue'

export default {
  name: 'SidebarAdmin',
  components: { SidebarAdminItem },
  props: {
    showSectionSeparators: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['activate'],
  computed: {
    adminTypes() {
      return this.$registry.getAll('admin')
    },
    sortedAdminTypes() {
      return Object.values(this.adminTypes)
        .filter((adminType) => adminType.isVisible())
        .slice()
        .sort((a, b) => a.getOrder() - b.getOrder())
    },
    groupedSortedAdminTypes() {
      const categories = []
      this.sortedAdminTypes.forEach((adminType) => {
        const categoryName = adminType.getCategory()
        let category = categories.find((c) => c.name === categoryName)
        if (!category) {
          category = { name: categoryName, items: [] }
          categories.push(category)
        }
        category.items.push(adminType)
      })
      return categories
    },
  },
}
</script>
