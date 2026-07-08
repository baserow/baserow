<template>
  <Tabs
    :selected-index="selectedTabIndex"
    full-height
    grow-items
    header-no-padding
    content-no-x-padding
    class="row-edit-modal-sidebar"
    @update:selected-index="onTabSelected"
  >
    <Tab
      v-for="sidebarType in sidebarTypes"
      :key="sidebarType.getType()"
      :title="sidebarType.getName()"
    >
      <component
        :is="sidebarType.getComponent()"
        :row="row"
        :table="table"
        :database="database"
        :fields="fields"
        :view="view"
      ></component>
    </Tab>
  </Tabs>
</template>

<script>
import Tabs from '@baserow/modules/core/components/Tabs.vue'
import Tab from '@baserow/modules/core/components/Tab.vue'
import {
  getRowEditModalSidebarTab,
  setRowEditModalSidebarTab,
} from '@baserow/modules/database/utils/rowEditModalSidebar'

export default {
  name: 'RowEditModalSidebar',
  components: {
    Tabs,
    Tab,
  },
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
    fields: {
      type: Array,
      required: true,
    },
    row: {
      type: Object,
      required: true,
    },
    view: {
      type: Object,
      required: false,
      default: null,
    },
    readOnly: {
      type: Boolean,
      required: false,
      default: false,
    },
  },
  data() {
    return {
      // Tab type currently shown. Starts at the initial (auto-opened) tab so
      // the mount echo is not persisted; updated on each real user selection.
      selectedType: null,
    }
  },
  computed: {
    selectedTabIndex() {
      const types = this.sidebarTypes
      const remembered = getRowEditModalSidebarTab()
      if (remembered) {
        const rememberedIndex = types.findIndex(
          (type) => type.getType() === remembered
        )
        if (rememberedIndex !== -1) {
          return rememberedIndex
        }
      }
      const index = types.findIndex((type) =>
        type.isSelectedByDefault(this.database, this.table)
      )
      return Math.max(index, 0)
    },
    sidebarTypes() {
      const allSidebarTypes = this.$registry.getOrderedList('rowModalSidebar')
      return allSidebarTypes.filter(
        (type) =>
          type.isDeactivated(
            this.database,
            this.table,
            this.readOnly,
            this.view
          ) === false && type.getComponent()
      )
    },
  },
  created() {
    this.selectedType =
      this.sidebarTypes[this.selectedTabIndex]?.getType() ?? null
  },
  methods: {
    // Persist the user's tab choice; skips the mount echo (same type as shown).
    onTabSelected(index) {
      const type = this.sidebarTypes[index]?.getType()
      if (type && type !== this.selectedType) {
        this.selectedType = type
        setRowEditModalSidebarTab(type)
      }
    },
  },
}
</script>
