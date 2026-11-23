<template>
  <Context
    ref="context"
    ph-autocapture="workspace-context"
    overflow-scroll
    max-height-if-outside-viewport
    @shown="fetchRolesAndPermissions"
  >
    <div v-if="showTitle" class="context__menu-title">
      {{ workspace.name }} ({{ workspace.id }})
    </div>
    <div
      v-if="workspace._.additionalLoading"
      class="loading margin-left-2 margin-top-2 margin-bottom-2"
    ></div>
    <slot v-else :actions="actions" :hide="hide">
      <ul class="context__menu">
        <WorkspaceActionItem :action="actions.exportData" />
        <WorkspaceActionItem :action="actions.importData" />
        <WorkspaceActionItem :action="actions.rename" />
        <WorkspaceActionItem :action="actions.settings" />
        <WorkspaceActionItem
          v-if="hasWorkspacePermission('invitation.read')"
          :action="actions.members"
        />
        <WorkspaceActionItem
          v-if="hasWorkspacePermission('workspace.read_trash')"
          :action="actions.trash"
        />
        <WorkspaceActionItem :action="actions.leave" />
        <WorkspaceActionItem :action="actions.delete" separator />
      </ul>
    </slot>

    <TrashModal ref="trashModal" :initial-workspace="workspace" />
    <ExportWorkspaceModal
      v-if="canExport"
      ref="exportModal"
      :workspace="workspace"
    />
    <ImportWorkspaceModal
      v-if="canExport"
      ref="importModal"
      :workspace="workspace"
    />
    <LeaveWorkspaceModal ref="leaveModal" :workspace="workspace" />
    <ConfirmModal
      v-if="actions.delete"
      ref="deleteModal"
      :title="$t('deleteWorkspaceModal.title', workspace)"
      :message="$t('deleteWorkspaceModal.confirmation', workspace)"
      :confirm-label="$t('workspaceContext.deleteWorkspace')"
      :loading="deleting"
      danger
      @confirm="deleteWorkspace"
    />
    <WorkspaceSettingsModal
      v-if="canUpdate"
      ref="settingsModal"
      :workspace="workspace"
    />
  </Context>
</template>

<script>
import context from '@baserow/modules/core/mixins/context'
import { notifyIf } from '@baserow/modules/core/utils/error'
import ExportWorkspaceModal from '@baserow/modules/core/components/export/ExportWorkspaceModal.vue'
import ImportWorkspaceModal from '@baserow/modules/core/components/import/ImportWorkspaceModal.vue'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import TrashModal from '@baserow/modules/core/components/trash/TrashModal'
import LeaveWorkspaceModal from '@baserow/modules/core/components/workspace/LeaveWorkspaceModal'
import WorkspaceActionItem from '@baserow/modules/core/components/workspace/WorkspaceActionItem.vue'
import WorkspaceSettingsModal from '@baserow/modules/core/components/workspace/WorkspaceSettingsModal'

export default {
  name: 'WorkspaceContext',
  components: {
    ConfirmModal,
    ExportWorkspaceModal,
    ImportWorkspaceModal,
    LeaveWorkspaceModal,
    TrashModal,
    WorkspaceActionItem,
    WorkspaceSettingsModal,
  },
  mixins: [context],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    showTitle: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['rename'],
  data() {
    return { deleting: false }
  },
  computed: {
    canExport() {
      return this.hasWorkspacePermission('workspace.export')
    },
    canUpdate() {
      return this.hasWorkspacePermission('workspace.update')
    },
    actions() {
      return {
        exportData: this.canExport
          ? {
              icon: 'iconoir-share-ios',
              label: 'workspaceContext.exportWorkspace',
              run: () => this.openModal('exportModal'),
            }
          : null,
        importData: this.canExport
          ? {
              icon: 'iconoir-import',
              label: 'workspaceContext.importWorkspace',
              run: () => this.openModal('importModal'),
            }
          : null,
        rename: this.canUpdate
          ? {
              icon: 'iconoir-edit-pencil',
              label: 'workspaceContext.renameWorkspace',
              run: () => this.$emit('rename'),
            }
          : null,
        settings: this.canUpdate
          ? {
              icon: 'iconoir-settings',
              label: 'workspaceContext.settings',
              run: () => this.openModal('settingsModal'),
            }
          : null,
        integrations: this.canUpdate
          ? {
              icon: 'iconoir-puzzle',
              label: 'sidebar.integrations',
              run: () => this.openModal('settingsModal', 'generative-ai'),
            }
          : null,
        members: {
          icon: 'baserow-icon-team',
          label: 'workspaceContext.members',
          to: {
            name: 'settings-members',
            params: { workspaceId: this.workspace.id },
          },
          run: () => this.hide(),
        },
        trash: {
          icon: 'iconoir-refresh-double',
          label: 'workspaceContext.viewTrash',
          run: () => this.openModal('trashModal'),
        },
        leave: {
          icon: 'iconoir-log-out',
          label: 'workspaceContext.leaveWorkspace',
          run: () => this.$refs.leaveModal.show(),
        },
        delete: this.hasWorkspacePermission('workspace.delete')
          ? {
              icon: 'iconoir-bin',
              label: 'workspaceContext.deleteWorkspace',
              run: () => this.openModal('deleteModal'),
              destructive: true,
            }
          : null,
      }
    },
  },
  methods: {
    hasWorkspacePermission(permission) {
      return this.$hasPermission(permission, this.workspace, this.workspace.id)
    },
    async fetchRolesAndPermissions() {
      const workspace = this.workspace
      try {
        await this.$store.dispatch('workspace/fetchPermissions', workspace)
        await this.$store.dispatch('workspace/fetchRoles', workspace)
      } catch (error) {
        this.$refs.context?.hide()
        notifyIf(error, 'workspace')
      }
    },
    openModal(ref, ...args) {
      this.hide()
      this.$refs[ref].show(...args)
    },
    async deleteWorkspace() {
      if (this.deleting) {
        return
      }
      this.deleting = true
      const workspace = this.workspace
      try {
        await this.$store.dispatch('workspace/delete', workspace)
        this.$refs.deleteModal?.hide()
        await this.$store.dispatch('toast/restore', {
          trash_item_type: 'workspace',
          trash_item_id: workspace.id,
        })
      } catch (error) {
        notifyIf(error, 'application')
      } finally {
        this.deleting = false
      }
    },
  },
}
</script>
