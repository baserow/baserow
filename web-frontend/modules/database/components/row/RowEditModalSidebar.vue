<template>
  <Tabs
    :selected-index="selectedTabIndex"
    full-height
    grow-items
    header-no-padding
    content-no-x-padding
    class="row-edit-modal-sidebar"
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
  computed: {
    selectedTabIndex() {
      const types = this.sidebarTypes
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
}
</script>
