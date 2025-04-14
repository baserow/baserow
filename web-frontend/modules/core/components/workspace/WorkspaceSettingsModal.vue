<template>
  <Modal
    :left-sidebar="true"
    :left-sidebar-scrollable="true"
    :content-scrollable="true"
  >
    <template #sidebar>
      <div class="modal-sidebar__title">
        {{ $t('workspaceSettingsModal.title') }}
      </div>
      <ul class="modal-sidebar__nav">
        <li v-for="setting in registeredSettings" :key="setting.type">
          <a
            class="modal-sidebar__nav-link"
            :class="{ active: page === setting.type }"
            @click="setPage(setting.type)"
          >
            <i class="modal-sidebar__nav-icon" :class="setting.iconClass"></i>
            {{ setting.getName() }}
          </a>
        </li>
      </ul>
    </template>
    <template #content>
      <component :is="settingPageComponent" :workspace="workspace"></component>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'

export default {
  name: 'WorkspaceSettingsModal',
  mixins: [modal],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      page: null,
    }
  },
  computed: {
    registeredSettings() {
      return this.$registry
        .getOrderedList('workspaceSettings')
        .filter((settings) => settings.isEnabled() === true)
    },
    settingPageComponent() {
      const active = Object.values(
        this.$registry.getAll('workspaceSettings')
      ).find((setting) => setting.type === this.page)
      return active ? active.getComponent() : null
    },
  },
  mounted() {
    this.setPage(
      Object.values(this.$registry.getOrderedList('workspaceSettings'))[0].type
    )
  },
  methods: {
    setPage(page) {
      this.page = page
    },
    isPage(page) {
      return this.page === page
    },
    show(page = null, ...args) {
      if (page === null) {
        const settings = Object.values(
          this.$registry.getAll('workspaceSettings')
        )
        this.page = settings.length > 0 ? settings[0].type : ''
      } else {
        this.page = page
      }
      return modal.methods.show.call(this, ...args)
    },
  },
}
</script>
