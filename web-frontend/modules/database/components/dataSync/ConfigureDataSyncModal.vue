<template>
  <Modal
    :left-sidebar="true"
    :left-sidebar-scrollable="true"
    @hidden="$emit('hidden')"
  >
    <template #sidebar>
      <div class="modal-sidebar__title">{{ table.name }}</div>
      <ul class="modal-sidebar__nav">
        <li v-for="page in pages" :key="page.getType()">
          <a
            class="modal-sidebar__nav-link"
            :class="{ active: selectedPage === page.getType() }"
            @click="setPage(page.getType())"
          >
            <i class="modal-sidebar__nav-icon" :class="page.iconClass"></i>
            {{ page.name }}
          </a>
        </li>
      </ul>
    </template>
    <template #content>
      <component
        :is="selectedPageObject.component"
        :database="database"
        :table="table"
        @hide="hide()"
      ></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

import ConfigureDataSyncVisibleFields from '@baserow/modules/database/components/dataSync/ConfigureDataSyncVisibleFields'
import ConfigureDataSyncSettings from '@baserow/modules/database/components/dataSync/ConfigureDataSyncSettings'

export default {
  name: 'ConfigureDataSyncModal',
  components: { ConfigureDataSyncVisibleFields, ConfigureDataSyncSettings },
  mixins: [modal],
  props: {
    database: {
      type: Object,
      required: true,
    },
    table: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      selectedPage: 'synced-fields',
    }
  },
  computed: {
    pages() {
      return Object.values(this.$registry.getAll('configureDataSync'))
    },
    selectedPageObject() {
      return this.pages.find((page) => page.getType() === this.selectedPage)
    },
  },
  methods: {
    show(selectedPage, ...args) {
      if (
        selectedPage &&
        this.$registry.exists('configureDataSync', selectedPage)
      ) {
        this.selectedPage = selectedPage
      }
      modal.methods.show.bind(this)(...args)
    },
    setPage(page) {
      this.selectedPage = page
    },
  },
}
</script>
