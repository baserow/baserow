<template>
  <Modal
    ref="modal"
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
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getEnabledWorkspaceSettings } from '@baserow/modules/core/workspaceSettingsTypes'

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
      return getEnabledWorkspaceSettings(
        this.$registry,
        this.workspace,
        this.$hasPermission(
          'workspace.update',
          this.workspace,
          this.workspace.id
        )
      )
    },
    settingPageComponent() {
      return this.registeredSettings
        .find((setting) => setting.type === this.page)
        ?.getComponent()
    },
  },
  mounted() {
    this.setPage(this.registeredSettings[0]?.type)
  },
  methods: {
    setPage(page) {
      this.page = page
    },
    isPage(page) {
      return this.page === page
    },
    show(page = null, ...args) {
      this.setPage(page ?? this.registeredSettings[0]?.type)
      this.fetchRolesAndPermissions()
      return modal.methods.show.call(this, ...args)
    },
    /**
     * Some pages are only there for people who can use them, which the
     * permissions of the workspace tell. They aren't loaded yet when the modal is
     * opened outside the workspace, like from the list of all workspaces.
     */
    async fetchRolesAndPermissions() {
      try {
        await this.$store.dispatch('workspace/fetchPermissions', this.workspace)
        await this.$store.dispatch('workspace/fetchRoles', this.workspace)
      } catch (error) {
        notifyIf(error, 'workspace')
      }
    },
  },
}
</script>
