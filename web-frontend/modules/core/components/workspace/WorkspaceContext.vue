<template>
  <Context
    ref="context"
    ph-autocapture="workspace-context"
    overflow-scroll
    max-height-if-outside-viewport
    @shown="fetchRolesAndPermissions"
  >
    <div class="context__menu-title">
      {{ workspace.name }} ({{ workspace.id }})
    </div>
    <div
      v-if="workspace._.additionalLoading"
      class="loading margin-left-2 margin-top-2 margin-bottom-2 margin-bottom-2"
    ></div>
    <ul v-else class="context__menu">
      <li
        v-if="$hasPermission('workspace.read', workspace, workspace.id)"
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="openExportData">
          <i class="context__menu-item-icon iconoir-share-ios"></i>
          {{ $t('workspaceContext.exportWorkspace') }}
        </a>
      </li>
      <li
        v-if="
          $hasPermission(
            'workspace.create_application',
            workspace,
            workspace.id
          )
        "
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="openImportData">
          <i class="context__menu-item-icon iconoir-import"></i>
          {{ $t('workspaceContext.importWorkspace') }}
        </a>
      </li>
      <li
        v-if="$hasPermission('workspace.update', workspace, workspace.id)"
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="$emit('rename')">
          <i class="context__menu-item-icon iconoir-edit-pencil"></i>
          {{ $t('workspaceContext.renameWorkspace') }}
        </a>
      </li>
      <li
        v-if="$hasPermission('workspace.update', workspace, workspace.id)"
        class="context__menu-item"
      >
        <a
          class="context__menu-item-link"
          @click="
            $refs.workspaceSettingsModal.show()
            hide()
          "
        >
          <i class="context__menu-item-icon iconoir-settings"></i>
          {{ $t('workspaceContext.settings') }}
        </a>
      </li>
      <li
        v-if="$hasPermission('invitation.read', workspace, workspace.id)"
        class="context__menu-item"
      >
        <a
          class="context__menu-item-link"
          @click="
            $router.push({
              name: 'settings-members',
              params: {
                workspaceId: workspace.id,
              },
            })
            hide()
          "
        >
          <i class="context__menu-item-icon iconoir-community"></i>
          {{ $t('workspaceContext.members') }}
        </a>
      </li>
      <li
        v-if="$hasPermission('workspace.read_trash', workspace, workspace.id)"
        class="context__menu-item"
      >
        <a class="context__menu-item-link" @click="showWorkspaceTrashModal">
          <i class="context__menu-item-icon iconoir-refresh-double"></i>
          {{ $t('workspaceContext.viewTrash') }}
        </a>
      </li>
      <li class="context__menu-item">
        <a
          class="context__menu-item-link"
          @click="$refs.leaveWorkspaceModal.show()"
        >
          <i class="context__menu-item-icon iconoir-log-out"></i>
          {{ $t('workspaceContext.leaveWorkspace') }}
        </a>
      </li>
      <li
        v-if="$hasPermission('workspace.delete', workspace, workspace.id)"
        class="context__menu-item context__menu-item--with-separator"
      >
        <a
          class="context__menu-item-link context__menu-item-link--delete"
          :class="{ 'context__menu-item-link--loading': loading }"
          @click="deleteWorkspace"
        >
          <i class="context__menu-item-icon iconoir-bin"></i>
          {{ $t('workspaceContext.deleteWorkspace') }}
        </a>
      </li>
    </ul>
    <TrashModal
      v-if="$hasPermission('workspace.read_trash', workspace, workspace.id)"
      ref="workspaceTrashModal"
      :initial-workspace="workspace"
    >
    </TrashModal>
    <ExportWorkspaceModal
      v-if="$hasPermission('workspace.read', workspace, workspace.id)"
      ref="exportWorkspaceModal"
      :workspace="workspace"
    >
    </ExportWorkspaceModal>
    <ImportWorkspaceModal
      v-if="
        $hasPermission('workspace.create_application', workspace, workspace.id)
      "
      ref="importWorkspaceModal"
      :workspace="workspace"
    ></ImportWorkspaceModal>
    <LeaveWorkspaceModal
      ref="leaveWorkspaceModal"
      :workspace="workspace"
    ></LeaveWorkspaceModal>
    <WorkspaceSettingsModal
      v-if="$hasPermission('workspace.update', workspace, workspace.id)"
      ref="workspaceSettingsModal"
      :workspace="workspace"
    ></WorkspaceSettingsModal>
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ExportWorkspaceModal from '@baserow/modules/core/components/export/ExportWorkspaceModal.vue'
import ImportWorkspaceModal from '@baserow/modules/core/components/import/ImportWorkspaceModal.vue'
import TrashModal from '@baserow/modules/core/components/trash/TrashModal'
import LeaveWorkspaceModal from '@baserow/modules/core/components/workspace/LeaveWorkspaceModal'
import WorkspaceSettingsModal from '@baserow/modules/core/components/workspace/WorkspaceSettingsModal'

export default {
  name: 'WorkspaceContext',
  components: {
    ExportWorkspaceModal,
    ImportWorkspaceModal,
    LeaveWorkspaceModal,
    TrashModal,
    WorkspaceSettingsModal,
  },
  mixins: [context],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async fetchRolesAndPermissions() {
      await this.$store.dispatch('workspace/fetchPermissions', this.workspace)
      await this.$store.dispatch('workspace/fetchRoles', this.workspace)
    },
    showWorkspaceTrashModal() {
      this.$refs.context.hide()
      this.$refs.workspaceTrashModal.show()
    },
    openExportData() {
      this.$refs.context.hide()
      this.$refs.exportWorkspaceModal.show()
    },
    openImportData() {
      this.$refs.context.hide()
      this.$refs.importWorkspaceModal.show()
    },
    async deleteWorkspace() {
      this.loading = true

      const selected =
        this.$store.getters['workspace/getSelected'].id === this.workspace.id

      try {
        await this.$store.dispatch('workspace/delete', this.workspace)
        await this.$store.dispatch('toast/restore', {
          trash_item_type: 'workspace',
          trash_item_id: this.workspace.id,
        })
        if (selected) {
          await this.$nuxt.$router.push({ name: 'dashboard' })
        }
        this.hide()
      } catch (error) {
        notifyIf(error, 'application')
      }

      this.loading = false
    },
  },
}
</script>
