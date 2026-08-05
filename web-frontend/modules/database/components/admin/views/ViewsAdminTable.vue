<template>
  <CrudTable
    ref="crudTable"
    :columns="columns"
    :service="service"
    row-id-key="id"
    :filters="filters"
    :default-search="defaultSearch"
    @row-context="onRowContext"
  >
    <template #title>
      {{ $t('viewsAdminTable.allViews') }}
    </template>
    <template #header-filters>
      <div class="data-table__filters">
        <SwitchInput v-model="onlyPublic" small>
          {{ $t('viewsAdminTable.onlyPublic') }}
        </SwitchInput>
        <PaginatedDropdown
          :key="`workspace-filter-${workspaceId}`"
          :value="workspaceId"
          :initial-display-name="workspaceName"
          :fetch-page="fetchWorkspaces"
          :empty-item-display-name="$t('viewsAdminTable.allWorkspaces')"
          :not-selected-text="$t('viewsAdminTable.allWorkspaces')"
          @input="selectWorkspace"
        ></PaginatedDropdown>
      </div>
    </template>
    <template #menus="slotProps">
      <ViewsAdminContext
        ref="viewsAdminContext"
        :view="editView"
        @update="slotProps.updateRow"
        @filter-workspace="filterWorkspace"
      ></ViewsAdminContext>
    </template>
  </CrudTable>
</template>

<script>
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import PaginatedDropdown from '@baserow/modules/core/components/PaginatedDropdown'
import { fetchWorkspaceOptions } from '@baserow/modules/core/services/admin/workspaces'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import LocalDateField from '@baserow/modules/core/components/crudTable/fields/LocalDateField'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import NameWithIdField from '@baserow/modules/core/components/crudTable/fields/NameWithIdField'
import BooleanIconField from '@baserow/modules/core/components/crudTable/fields/BooleanIconField'
import ViewsAdminService from '@baserow/modules/database/services/admin/views'
import ViewTypeField from '@baserow/modules/database/components/admin/views/fields/ViewTypeField'
import ViewsAdminContext from '@baserow/modules/database/components/admin/views/contexts/ViewsAdminContext'

export default {
  name: 'ViewsAdminTable',
  components: {
    CrudTable,
    PaginatedDropdown,
    ViewsAdminContext,
  },
  data() {
    this.service = ViewsAdminService(this.$client)
    return {
      editView: {},
      onlyPublic: true,
      workspaceId: null,
      workspaceName: null,
    }
  },
  computed: {
    defaultSearch() {
      const { search } = this.$route.query
      return search ? String(search) : null
    },
    filters() {
      const filters = {}
      if (this.onlyPublic) {
        filters.only_public = 'true'
      }
      if (this.workspaceId !== null) {
        filters.workspace_id = String(this.workspaceId)
      }
      return filters
    },
    columns() {
      return [
        new CrudTableColumn(
          'name',
          () => this.$t('viewsAdminTable.name'),
          NameWithIdField,
          true,
          true,
          false,
          { idKey: 'id' }
        ),
        new CrudTableColumn(
          'type',
          () => this.$t('viewsAdminTable.type'),
          ViewTypeField,
          true
        ),
        new CrudTableColumn(
          'table_name',
          () => this.$t('viewsAdminTable.table'),
          NameWithIdField,
          false,
          false,
          false,
          { idKey: 'table_id' }
        ),
        new CrudTableColumn(
          'database_name',
          () => this.$t('viewsAdminTable.database'),
          NameWithIdField,
          true,
          false,
          false,
          { idKey: 'database_id' }
        ),
        new CrudTableColumn(
          'workspace_name',
          () => this.$t('viewsAdminTable.workspace'),
          NameWithIdField,
          true,
          false,
          false,
          { idKey: 'workspace_id', navigateRoute: 'admin-workspaces' }
        ),
        new CrudTableColumn(
          'public',
          () => this.$t('viewsAdminTable.public'),
          BooleanIconField,
          true,
          false,
          false,
          {
            icon: 'iconoir-globe',
            title: this.$t('viewsAdminTable.public'),
          }
        ),
        new CrudTableColumn(
          'public_view_has_password',
          () => this.$t('viewsAdminTable.passwordProtected'),
          BooleanIconField,
          false,
          false,
          false,
          {
            icon: 'iconoir-lock',
            title: this.$t('viewsAdminTable.passwordProtected'),
          }
        ),
        new CrudTableColumn(
          'owned_by_username',
          () => this.$t('viewsAdminTable.ownedBy'),
          NameWithIdField,
          true,
          false,
          false,
          { idKey: 'owned_by_id', navigateRoute: 'admin-users' }
        ),
        new CrudTableColumn(
          'created_on',
          () => this.$t('viewsAdminTable.createdOn'),
          LocalDateField,
          true
        ),
        new CrudTableColumn('more', '', MoreField, false, false, true),
      ]
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

      const action = row.id === this.editView.id ? 'toggle' : 'show'
      this.editView = row
      this.$refs.viewsAdminContext[action](target, 'bottom', 'left', 4)
    },
    fetchWorkspaces(page, search) {
      return fetchWorkspaceOptions(this.$client, page, search)
    },
    selectWorkspace(workspaceId) {
      // The dropdown keeps its own display name once something is picked from its
      // list, so nothing has to be resolved here.
      this.workspaceId = workspaceId
      this.workspaceName = null
    },
    async filterWorkspace({ id, name }) {
      this.workspaceId = id
      this.workspaceName = name
      await this.$nextTick()
      this.$refs.crudTable.setSearch('')
    },
  },
}
</script>
