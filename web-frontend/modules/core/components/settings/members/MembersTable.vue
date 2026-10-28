<template>
  <div>
    <CrudTable
      v-bind="tableLayout"
      ref="crudTable"
      class="management-table"
      :service="service"
      :columns="columns"
      row-id-key="id"
      :search-placeholder="$t('membersSettings.membersTable.search')"
      :row-expandable="rowExpansion?.isExpandable"
      :expand-column-key="rowExpansion?.columnKey"
      @row-context="onRowContext"
      @edit-role-context="onEditRoleContext"
    >
      <template v-if="rowExpansion" #row-expansion-toggle="{ row }">
        {{ rowExpansion.getToggleLabel(row) }}
      </template>
      <template v-if="rowExpansion" #expanded-row="slotProps">
        <component
          :is="rowExpansion.component"
          v-bind="{ ...slotProps, ...rowExpansion.getProps(slotProps.row) }"
          :workspace="workspace"
        />
      </template>
      <template #title>
        {{
          $t('membersSettings.membersTable.title', {
            userAmount: membersCount,
            workspaceName: workspace.name,
          })
        }}
      </template>
      <template #empty>
        <div class="placeholder">
          <div class="placeholder__icon">
            <i class="baserow-icon-team" aria-hidden="true"></i>
          </div>
          <h2 class="placeholder__header">
            {{ $t('membersSettings.membersTable.emptyTitle') }}
          </h2>
          <p class="placeholder__content">
            {{ $t('membersSettings.membersTable.emptyDescription') }}
          </p>
        </div>
      </template>
      <template #header-right-side>
        <Button
          v-if="canInvite && pendingInvitationsCount > 0"
          type="secondary"
          size="large"
          icon="iconoir-mail"
          @click="$refs.inviteModal.show()"
        >
          {{
            $t('membersSettings.membersTable.pendingInvitations', {
              count: pendingInvitationsCount,
            })
          }}
        </Button>
      </template>
      <template #primary-action>
        <Button
          v-if="canInvite"
          type="primary"
          size="large"
          icon="iconoir-plus"
          @click="$refs.inviteModal.show()"
        >
          {{ $t('membersSettings.membersTable.inviteMember') }}
        </Button>
      </template>
      <template #menus="slotProps">
        <EditMemberContext
          ref="editMemberContext"
          :workspace="workspace"
          :member="editMember"
          @remove-user="slotProps.deleteRow"
        ></EditMemberContext>
        <EditRoleContext
          ref="editRoleContext"
          :subject="editRoleMember"
          :roles="roles"
          :workspace="workspace"
          @update-role="roleUpdate($event)"
        ></EditRoleContext>
      </template>
    </CrudTable>
    <InviteModal ref="inviteModal" :workspace="workspace" />
  </div>
</template>

<script>
import { getManagementTableLayout } from '@baserow/modules/core/utils/managementTable'
import { mapGetters } from 'vuex'
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { getWorkspaceMembersCount } from '@baserow/modules/core/utils/workspace'

import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import ManagementNameField from '@baserow/modules/core/components/settings/ManagementNameField'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import MemberTwoFactorAuthField from '@baserow/modules/core/components/settings/members/MemberTwoFactorAuthField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import MemberRoleField from '@baserow/modules/core/components/settings/members/MemberRoleField'
import InviteModal from '@baserow/modules/core/components/invitation/InviteModal'
import EditMemberContext from '@baserow/modules/core/components/settings/members/EditMemberContext'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'

export default {
  name: 'MembersTable',
  components: {
    EditMemberContext,
    EditRoleContext,
    CrudTable,
    InviteModal,
  },
  props: {
    workspace: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      editMember: {},
      editRoleMember: {},
      pendingInvitationsCount: 0,
    }
  },
  computed: {
    tableLayout() {
      return getManagementTableLayout(
        this.columns,
        this.rowExpansion?.columnKey || 'permissions'
      )
    },
    ...mapGetters({ userId: 'auth/getUserId' }),
    canInvite() {
      return this.$hasPermission(
        'workspace.create_invitation',
        this.workspace,
        this.workspace.id
      )
    },
    canListInvitations() {
      return this.$hasPermission(
        'workspace.list_invitations',
        this.workspace,
        this.workspace.id
      )
    },
    membersCount() {
      return getWorkspaceMembersCount(
        this.workspace,
        this.$hasPermission(
          'workspace.list_agents',
          this.workspace,
          this.workspace.id
        )
      )
    },
    roles() {
      return this.workspace._.roles
    },
    service() {
      const service = WorkspaceService(this.$client)
      const options = {
        ...service.options,
        urlParams: { workspaceId: this.workspace.id },
      }
      return {
        ...service,
        options,
      }
    },
    membersPagePlugins() {
      return Object.values(this.$registry.getAll('membersPagePlugins'))
    },
    /**
     * How a member's row expands into more rows, as given by the first active
     * plugin offering it, or null.
     */
    rowExpansion() {
      for (const plugin of this.membersPagePlugins) {
        if (!plugin.isDeactivated(this.workspace.id)) {
          const expansion = plugin.getRowExpansion({
            workspace: this.workspace,
          })
          if (expansion) {
            return expansion
          }
        }
      }
      return null
    },
    columns() {
      let columns = [
        new CrudTableColumn(
          'name',
          this.$t('membersSettings.membersTable.columns.name'),
          ManagementNameField,
          true,
          true,
          false,
          {
            userId: this.userId,
            avatarComponent: this.$registry.get('subject', 'auth.User')
              .avatarComponent,
          }
        ),
        new CrudTableColumn(
          'email',
          this.$t('membersSettings.membersTable.columns.email'),
          SimpleField,
          true
        ),
        new CrudTableColumn(
          'permissions',
          this.$t('membersSettings.membersTable.columns.role'),
          MemberRoleField,
          false,
          false,
          false,
          {
            roles: this.roles,
            userId: this.userId,
            workspaceId: this.workspace.id,
          }
        ),
        new CrudTableColumn(
          'two_factor_auth',
          this.$t('membersSettings.membersTable.columns.2fa'),
          MemberTwoFactorAuthField,
          false
        ),
        new CrudTableColumn(null, null, MoreField, false, false, true),
      ]
      for (const plugin of this.membersPagePlugins) {
        if (!plugin.isDeactivated(this.workspace.id)) {
          columns = plugin.mutateMembersTableColumns(columns, {
            workspace: this.workspace,
            client: this.$client,
          })
        }
      }
      return columns
    },
  },
  watch: {
    'workspace.id'() {
      this.fetchPendingInvitationsCount()
    },
  },
  beforeMount() {
    this.$bus.$on('invite-submitted', this.refreshPendingInvitationsCount)
    this.$bus.$on('invite-updated', this.refreshPendingInvitationsCount)
    this.$bus.$on('invite-deleted', this.refreshPendingInvitationsCount)
  },
  mounted() {
    this.fetchPendingInvitationsCount()
  },
  beforeUnmount() {
    this.$bus.$off('invite-submitted', this.refreshPendingInvitationsCount)
    this.$bus.$off('invite-updated', this.refreshPendingInvitationsCount)
    this.$bus.$off('invite-deleted', this.refreshPendingInvitationsCount)
  },
  methods: {
    /**
     * The pending invitations are managed in the invite modal, so they're only
     * counted for those who can both open it and list them.
     */
    async fetchPendingInvitationsCount() {
      if (!this.canInvite || !this.canListInvitations) {
        this.pendingInvitationsCount = 0
        return
      }
      try {
        const { data } = await WorkspaceService(
          this.$client
        ).fetchAllInvitations(this.workspace.id)
        this.pendingInvitationsCount = data.length
      } catch (error) {
        notifyIf(error, 'workspace')
      }
    },
    refreshPendingInvitationsCount(invitation) {
      if (invitation.workspace === this.workspace.id) {
        this.fetchPendingInvitationsCount()
      }
    },
    onRowContext({ row, event, target }) {
      event.preventDefault()
      if (target === undefined) {
        target = {
          left: event.clientX,
          top: event.clientY,
        }
      }

      const action = row.id === this.editMember.id ? 'toggle' : 'show'
      this.editMember = row
      this.$refs.editMemberContext[action](target, 'bottom', 'left', 4)
    },
    onEditRoleContext({ row, target }) {
      const action = row.id === this.editRoleMember.id ? 'toggle' : 'show'
      this.editRoleMember = row
      this.$refs.editRoleContext[action](target, 'bottom', 'left', 4)
    },
    async roleUpdate({ uid: permissionsNew, subject: member }) {
      const oldMember = clone(member)
      const newMember = clone(member)
      newMember.permissions = permissionsNew
      this.$refs.crudTable.updateRow(newMember)

      try {
        await WorkspaceService(this.$client).updateUser(oldMember.id, {
          permissions: newMember.permissions,
        })
        await this.$store.dispatch('workspace/forceUpdateWorkspaceUser', {
          workspaceId: this.workspace.id,
          id: oldMember.id,
          values: { permissions: newMember.permissions },
        })
      } catch (error) {
        this.$refs.crudTable.updateRow(oldMember)
        notifyIf(error, 'workspace')
      }
    },
  },
}
</script>
