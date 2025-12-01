<template>
  <div>
    <CrudTable
      ref="crudTable"
      :service="service"
      :columns="columns"
      row-id-key="id"
      @row-context="onRowContext"
      @edit-role-context="onEditRoleContext"
    >
      <template #title>
        {{
          $t('membersSettings.membersTable.title', {
            userAmount: workspace.users.length || 0,
            workspaceName: workspace.name,
          })
        }}
      </template>
      <template #header-right-side>
        <Button
          v-if="
            $hasPermission(
              'workspace.create_invitation',
              workspace,
              workspace.id
            )
          "
          type="primary"
          size="large"
          class="margin-left-2"
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
    <WorkspaceMemberInviteModal
      ref="inviteModal"
      :workspace="workspace"
      @invite-submitted="
        $router.push({
          name: 'settings-invites',
          params: {
            workspaceId: workspace.id,
          },
        })
      "
    />
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { clone } from '@baserow/modules/core/utils/object'
import { notifyIf } from '@baserow/modules/core/utils/error'

import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import TwoFactorAuthField from '@baserow/modules/core/components/crudTable/fields/TwoFactorAuthField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import MemberRoleField from '@baserow/modules/core/components/settings/members/MemberRoleField'
import WorkspaceMemberInviteModal from '@baserow/modules/core/components/workspace/WorkspaceMemberInviteModal'
import EditMemberContext from '@baserow/modules/core/components/settings/members/EditMemberContext'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'

export default {
  name: 'MembersTable',
  components: {
    EditMemberContext,
    EditRoleContext,
    CrudTable,
    WorkspaceMemberInviteModal,
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
    }
  },
  computed: {
    ...mapGetters({ userId: 'auth/getUserId' }),
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
    columns() {
      let columns = [
        new CrudTableColumn(
          'name',
          this.$t('membersSettings.membersTable.columns.name'),
          SimpleField,
          true,
          true
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
          TwoFactorAuthField,
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
  methods: {
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
