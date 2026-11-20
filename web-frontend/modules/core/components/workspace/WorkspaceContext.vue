<template>
  <Context
    ref="context"
    ph-autocapture="workspace-context"
    overflow-scroll
    max-height-if-outside-viewport
    @shown="fetchRolesAndPermissions"
  >
    <div v-if="!sidebar" class="context__menu-title">
      {{ workspace.name }} ({{ workspace.id }})
    </div>
    <div
      v-if="workspace._.additionalLoading"
      class="loading margin-left-2 margin-top-2 margin-bottom-2 margin-bottom-2"
    ></div>
    <ul v-else class="context__menu">
      <template v-for="action in actions" :key="action">
        <li v-if="action === 'invite' && canInvite" class="context__menu-item">
          <button
            type="button"
            class="context__menu-item-link"
            @click="openModal('inviteModal')"
          >
            <i class="context__menu-item-icon iconoir-add-user"></i>
            {{ $t('sidebar.inviteOthers') }}
          </button>
        </li>
        <li
          v-else-if="
            action === 'separator' ||
            (action === 'invite-separator' && canInvite)
          "
          class="sidebar-workspace-menu__separator"
          role="separator"
        ></li>
        <li
          v-else-if="action === 'export' && canExport"
          class="context__menu-item"
        >
          <button
            type="button"
            class="context__menu-item-link workspace-context__action"
            @click="openModal('exportWorkspaceModal')"
          >
            <i class="context__menu-item-icon iconoir-share-ios"></i>
            {{ $t('workspaceContext.exportWorkspace') }}
          </button>
        </li>
        <li
          v-else-if="action === 'import' && canExport"
          class="context__menu-item"
        >
          <button
            type="button"
            class="context__menu-item-link workspace-context__action"
            @click="openModal('importWorkspaceModal')"
          >
            <i class="context__menu-item-icon iconoir-import"></i>
            {{ $t('workspaceContext.importWorkspace') }}
          </button>
        </li>
        <li
          v-else-if="action === 'rename' && canUpdate"
          class="context__menu-item"
        >
          <button
            type="button"
            class="context__menu-item-link workspace-context__action"
            @click="
              sidebar ? openModal('renameWorkspaceModal') : $emit('rename')
            "
          >
            <i class="context__menu-item-icon iconoir-edit-pencil"></i>
            {{ $t('workspaceContext.renameWorkspace') }}
          </button>
        </li>
        <li
          v-else-if="action === 'settings' && canUpdate"
          class="context__menu-item"
        >
          <button
            type="button"
            class="context__menu-item-link workspace-context__action"
            @click="openModal('workspaceSettingsModal')"
          >
            <i
              class="context__menu-item-icon"
              :class="sidebar ? 'iconoir-puzzle' : 'iconoir-settings'"
            ></i>
            {{
              $t(
                sidebar
                  ? 'workspaceSettingType.aiProviders'
                  : 'workspaceContext.settings'
              )
            }}
          </button>
        </li>
        <li
          v-else-if="action === 'members' && canListMembers"
          class="context__menu-item"
        >
          <nuxt-link
            v-if="sidebar"
            class="context__menu-item-link"
            :to="membersRoute"
            prefetch-on="interaction"
            @click="hide()"
          >
            <i class="context__menu-item-icon baserow-icon-team"></i>
            {{ $t('workspaceContext.members') }}
          </nuxt-link>
          <button
            v-else
            type="button"
            class="context__menu-item-link workspace-context__action"
            @click="($router.push(membersRoute), hide())"
          >
            <i class="context__menu-item-icon baserow-icon-team"></i>
            {{ $t('workspaceContext.members') }}
          </button>
        </li>
        <template v-else-if="action === 'before-trash'">
          <slot name="before-trash" :hide="hide"></slot>
        </template>
        <li
          v-else-if="action === 'trash' && canReadTrash"
          class="context__menu-item"
        >
          <button
            type="button"
            class="context__menu-item-link workspace-context__action"
            @click="openModal('workspaceTrashModal')"
          >
            <i
              class="context__menu-item-icon"
              :class="sidebar ? 'iconoir-bin' : 'iconoir-refresh-double'"
            ></i>
            {{ $t('workspaceContext.viewTrash') }}
          </button>
        </li>
        <li v-else-if="action === 'leave'" class="context__menu-item">
          <button
            type="button"
            class="context__menu-item-link workspace-context__action"
            @click="
              sidebar
                ? openModal('leaveWorkspaceModal')
                : $refs.leaveWorkspaceModal.show()
            "
          >
            <i class="context__menu-item-icon iconoir-log-out"></i>
            {{ $t('workspaceContext.leaveWorkspace') }}
          </button>
        </li>
        <li
          v-else-if="
            action === 'delete' &&
            $hasPermission('workspace.delete', workspace, workspace.id)
          "
          class="context__menu-item context__menu-item--with-separator"
        >
          <button
            type="button"
            class="context__menu-item-link context__menu-item-link--delete workspace-context__action"
            :class="{ 'context__menu-item-link--loading': loading }"
            @click="deleteWorkspace"
          >
            <i class="context__menu-item-icon iconoir-bin"></i>
            {{ $t('workspaceContext.deleteWorkspace') }}
          </button>
        </li>
      </template>
    </ul>
    <InviteModal
      v-if="sidebar && canInvite"
      ref="inviteModal"
      :workspace="workspace"
    />
    <Modal v-if="sidebar && canUpdate" ref="renameWorkspaceModal">
      <h2 class="box__title">{{ $t('workspaceContext.renameWorkspace') }}</h2>
      <WorkspaceForm
        :default-name="workspace.name"
        @submitted="renameWorkspace"
      >
        <div class="actions">
          <div class="align-right">
            <Button type="primary" :loading="renaming" :disabled="renaming">
              {{ $t('action.save') }}
            </Button>
          </div>
        </div>
      </WorkspaceForm>
    </Modal>
    <TrashModal
      v-if="canReadTrash"
      ref="workspaceTrashModal"
      :initial-workspace="workspace"
    >
    </TrashModal>
    <ExportWorkspaceModal
      v-if="canExport"
      ref="exportWorkspaceModal"
      :workspace="workspace"
    >
    </ExportWorkspaceModal>
    <ImportWorkspaceModal
      v-if="canExport"
      ref="importWorkspaceModal"
      :workspace="workspace"
    ></ImportWorkspaceModal>
    <LeaveWorkspaceModal
      ref="leaveWorkspaceModal"
      :workspace="workspace"
    ></LeaveWorkspaceModal>
    <WorkspaceSettingsModal
      v-if="canUpdate"
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
import WorkspaceForm from '@baserow/modules/core/components/workspace/WorkspaceForm'
import InviteModal from '@baserow/modules/core/components/invitation/InviteModal'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick, useNuxtApp } from '#imports'

export default {
  name: 'WorkspaceContext',
  components: {
    ExportWorkspaceModal,
    ImportWorkspaceModal,
    LeaveWorkspaceModal,
    TrashModal,
    WorkspaceSettingsModal,
    WorkspaceForm,
    InviteModal,
  },
  mixins: [context],
  props: {
    workspace: {
      type: Object,
      required: true,
    },
    sidebar: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['rename'],
  setup() {
    const nuxtApp = useNuxtApp()
    return { nuxtApp }
  },
  data() {
    return {
      loading: false,
      renaming: false,
    }
  },
  computed: {
    actions() {
      return this.sidebar
        ? [
            'invite',
            'invite-separator',
            'members',
            'settings',
            'before-trash',
            'trash',
            'separator',
            'export',
            'import',
            'rename',
            'leave',
            'delete',
          ]
        : [
            'export',
            'import',
            'rename',
            'settings',
            'members',
            'trash',
            'leave',
            'delete',
          ]
    },
    canInvite() {
      return this.$hasPermission(
        'workspace.create_invitation',
        this.workspace,
        this.workspace.id
      )
    },
    canExport() {
      return this.$hasPermission(
        'workspace.export',
        this.workspace,
        this.workspace.id
      )
    },
    canUpdate() {
      return this.$hasPermission(
        'workspace.update',
        this.workspace,
        this.workspace.id
      )
    },
    canListMembers() {
      return this.$hasPermission(
        this.sidebar ? 'workspace.list_workspace_users' : 'invitation.read',
        this.workspace,
        this.workspace.id
      )
    },
    canReadTrash() {
      return (
        this.sidebar ||
        this.$hasPermission(
          'workspace.read_trash',
          this.workspace,
          this.workspace.id
        )
      )
    },
    membersRoute() {
      return {
        name: 'settings-members',
        params: { workspaceId: this.workspace.id },
      }
    },
  },
  methods: {
    async fetchRolesAndPermissions() {
      try {
        await this.$store.dispatch('workspace/fetchPermissions', this.workspace)
        await this.$store.dispatch('workspace/fetchRoles', this.workspace)
      } catch (error) {
        this.$refs.context.hide()
        notifyIf(error, 'workspace')
      }
    },
    openModal(ref) {
      this.hide()
      this.$refs[ref].show()
    },
    async renameWorkspace(values) {
      this.renaming = true
      try {
        await this.$store.dispatch('workspace/update', {
          workspace: this.workspace,
          values,
        })
        this.$refs.renameWorkspaceModal?.hide()
      } catch (error) {
        notifyIf(error, 'workspace')
      } finally {
        this.renaming = false
      }
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
          await this.$router.push({ name: 'all-workspaces' })
          await pageFinished(this.nuxtApp)
          await nextTick()
        }
      } catch (error) {
        notifyIf(error, 'application')
      }

      this.loading = false
    },
  },
}
</script>
