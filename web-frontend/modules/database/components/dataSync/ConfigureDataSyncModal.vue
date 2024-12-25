<template>
  <Modal :left-sidebar="true" :left-sidebar-scrollable="true">
    <template #sidebar>
      <div class="modal-sidebar__head">
        <div class="modal-sidebar__head-name">
          {{ table.name }}
        </div>
      </div>
      <ul class="modal-sidebar__nav">
        <li v-for="page in pages" :key="page.type">
          <a
            class="modal-sidebar__nav-link"
            :class="{ active: selectedPage === page.type }"
            @click="setPage(page.type)"
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
      pages: [
        {
          type: 'visible-fields',
          name: this.$t('configureDataSyncModal.syncedFields'),
          iconClass: 'iconoir-switch-on',
          component: ConfigureDataSyncVisibleFields,
        },
        {
          type: 'settings',
          name: this.$t('configureDataSyncModal.syncSettings'),
          iconClass: 'iconoir-settings',
          component: ConfigureDataSyncSettings,
        },
      ],
      selectedPage: 'visible-fields',
    }
  },
  computed: {
    selectedPageObject() {
      return this.pages.find((page) => page.type === this.selectedPage)
    },
  },
  methods: {
    setPage(page) {
      this.selectedPage = page
    },
  },
}
</script>
