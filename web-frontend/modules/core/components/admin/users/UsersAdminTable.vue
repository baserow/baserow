<template>
  <CrudTable
    :columns="columns"
    :service="service"
    row-id-key="id"
    @row-context="onRowContext"
  >
    <template #title>
      {{ $t('usersAdminTable.allUsers') }}
    </template>
    <template #menus="slotProps">
      <EditUserContext
        ref="editUserContext"
        :user="editUser"
        @delete-user="slotProps.deleteRow"
        @update="slotProps.updateRow"
      >
      </EditUserContext>
    </template>
  </CrudTable>
</template>

<script>
import UserAdminService from '@baserow/modules/core/services/admin/users'
import UsernameField from '@baserow/modules/core/components/admin/users/fields/UsernameField'
import UserWorkspacesField from '@baserow/modules/core/components/admin/users/fields/UserWorkspacesField'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
import LocalDateField from '@baserow/modules/core/components/crudTable/fields/LocalDateField'
import ActiveField from '@baserow/modules/core/components/admin/users/fields/ActiveField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import EditUserContext from '@baserow/modules/core/components/admin/users/contexts/EditUserContext'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'

export default {
  name: 'UsersAdminTable',
  components: {
    CrudTable,
    EditUserContext,
  },
  data() {
    this.service = UserAdminService(this.$client)
    return {
      editUser: {},
    }
  },
  computed: {
    membersPagePlugins() {
      return Object.values(this.$registry.getAll('membersPagePlugins'))
    },
    columns() {
      let columns = [
        new CrudTableColumn(
          'username',
          () => this.$t('usersAdminTable.username'),
          UsernameField,
          true,
          true
        ),
        new CrudTableColumn(
          'name',
          () => this.$t('usersAdminTable.name'),
          SimpleField,
          true
        ),
        new CrudTableColumn(
          'workspaces',
          () => this.$t('usersAdminTable.workspaces'),
          UserWorkspacesField
        ),
        new CrudTableColumn(
          'last_login',
          () => this.$t('usersAdminTable.lastLogin'),
          LocalDateField,
          true
        ),
        new CrudTableColumn(
          'date_joined',
          () => this.$t('usersAdminTable.dateJoined'),
          LocalDateField,
          true
        ),
        new CrudTableColumn(
          'is_active',
          () => this.$t('user.active'),
          ActiveField,
          true
        ),
        new CrudTableColumn('more', '', MoreField, false, false, true),
      ]
      for (const plugin of this.membersPagePlugins) {
        if (!plugin.isDeactivated()) {
          columns = plugin.mutateAdminUsersTableColumns(columns, {
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

      const action = row.id === this.editUser.id ? 'toggle' : 'show'
      this.editUser = row
      this.$refs.editUserContext[action](target, 'bottom', 'left', 4)
    },
  },
}
</script>
