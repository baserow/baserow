<template>
  <div>
    <CrudTable
      ref="crudTable"
      :service="service"
      :columns="columns"
      row-id-key="id"
      @rows-update="invitesAmount = $event.length"
      @row-context="onRowContext"
      @edit-role-context="onEditRoleContext"
    >
      <template #title>
        {{
          $t('membersSettings.invitesTable.title', {
            invitesAmount,
            workspaceName: workspace.name,
          })
        }}
      </template>
      <template #header-right-side>
        <Button
          type="primary"
          size="large"
          class="margin-left-2"
          @click="$refs.inviteModal.show()"
        >
          {{ $t('membersSettings.membersTable.inviteMember') }}
        </Button>
      </template>
      <template #menus>
        <EditInviteContext
          ref="editInviteContext"
          :invitation="editInvitation"
          @refresh="$refs.crudTable.fetch()"
        ></EditInviteContext>
        <EditRoleContext
          ref="editRoleContext"
          :workspace="workspace"
          :subject="editRoleInvitation"
          :roles="roles"
          @update-role="roleUpdate($event)"
        ></EditRoleContext>
      </template>
    </CrudTable>
    <WorkspaceMemberInviteModal ref="inviteModal" :workspace="workspace" />
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import WorkspaceService from '@baserow/modules/core/services/workspace'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import WorkspaceMemberInviteModal from '@baserow/modules/core/components/workspace/WorkspaceMemberInviteModal'
import EditInviteContext from '@baserow/modules/core/components/settings/members/EditInviteContext'
import MemberRoleField from '@baserow/modules/core/components/settings/members/MemberRoleField'
import EditRoleContext from '@baserow/modules/core/components/settings/members/EditRoleContext'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'MembersInvitesTable',
  components: {
    EditInviteContext,
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
      editInvitation: {},
      editRoleInvitation: {},
      invitesAmount: 0,
    }
  },
  computed: {
    roles() {
      return this.workspace._.roles
    },
    service() {
      const service = WorkspaceService(this.$client)

      service.options.baseUrl = ({ workspaceId }) =>
        `/workspaces/invitations/workspace/${workspaceId}/`

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
          'email',
          this.$t('membersSettings.invitesTable.columns.email'),
          SimpleField,
          true,
          true
        ),
        new CrudTableColumn(
          'message',
          this.$t('membersSettings.invitesTable.columns.message'),
          SimpleField,
          true
        ),
        new CrudTableColumn(
          'permissions',
          this.$t('membersSettings.invitesTable.columns.role'),
          MemberRoleField,
          false,
          false,
          false,
          {
            roles: this.roles,
            userId: 0,
            workspaceId: this.workspace.id,
          }
        ),
        new CrudTableColumn(null, null, MoreField, false, false, true),
      ]
      for (const plugin of this.membersPagePlugins) {
        if (!plugin.isDeactivated(this.workspace.id)) {
          columns = plugin.mutateMembersInvitesTableColumns(columns, {
            workspace: this.workspace,
          })
        }
      }

      return columns
    },
  },
  beforeMount() {
    this.$bus.$on('invite-submitted', this.inviteSubmitted)
  },
  beforeUnmount() {
    this.$bus.$off('invite-submitted', this.inviteSubmitted)
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

      const action = row.id === this.editInvitation.id ? 'toggle' : 'show'
      this.editInvitation = row
      this.$refs.editInviteContext[action](target, 'bottom', 'left', 4)
    },
    onEditRoleContext({ row, target }) {
      const action = row.id === this.editRoleInvitation.id ? 'toggle' : 'show'
      this.editRoleInvitation = row
      this.$refs.editRoleContext[action](target, 'bottom', 'left', 4)
    },
    async roleUpdate({ uid: permissionsNew, subject: invitation }) {
      const oldInvitation = clone(invitation)
      const newInvitation = clone(invitation)
      newInvitation.permissions = permissionsNew
      this.$refs.crudTable.updateRow(newInvitation)

      try {
        await WorkspaceService(this.$client).updateInvitation(invitation.id, {
          permissions: permissionsNew,
        })
      } catch (error) {
        this.$refs.crudTable.updateRow(oldInvitation)
        notifyIf(error, 'workspace')
      }
    },
    inviteSubmitted(values) {
      this.$refs.crudTable.upsertRow(values)
    },
  },
}
</script>
