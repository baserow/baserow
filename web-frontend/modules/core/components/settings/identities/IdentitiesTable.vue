<template>
  <CrudTable
    v-bind="tableLayout"
    ref="table"
    class="management-table management-table--identities"
    :service="service"
    :columns="columns"
    row-id-key="id"
    :search-placeholder="$t('identities.search')"
    :row-expandable="rowExpansion?.isExpandable"
    :expand-column-key="rowExpansion?.columnKey"
    @row-context="openContext"
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
    <template #title="{ count }">{{
      $t('identities.title', { count, workspace: workspace.name })
    }}</template>
    <template #empty>
      <div class="placeholder">
        <div class="placeholder__icon">
          <i class="iconoir-lock" aria-hidden="true"></i>
        </div>
        <h2 class="placeholder__header">{{ $t('identities.emptyTitle') }}</h2>
        <p class="placeholder__content">
          {{ $t('identities.emptyDescription') }}
        </p>
      </div>
    </template>
    <template #primary-action>
      <Button
        v-if="canCreate"
        type="primary"
        size="large"
        icon="iconoir-plus"
        @click="$refs.createModal.show()"
      >
        {{ $t('identities.create') }}
      </Button>
    </template>
    <template #menus>
      <IdentityContext
        v-if="focusedIdentity && canManage"
        ref="context"
        :identity="focusedIdentity"
        :can-update="canUpdate"
        :can-delete="canDelete"
        @edit="$refs.updateModal.show()"
      />
    </template>
  </CrudTable>
  <ManageIdentityModal ref="createModal" :workspace="workspace" />
  <ManageIdentityModal
    v-if="focusedIdentity && canUpdate"
    ref="updateModal"
    :workspace="workspace"
    :identity="focusedIdentity"
  />
</template>

<script>
import { getManagementTableLayout } from '@baserow/modules/core/utils/managementTable'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import ManagementNameField from '@baserow/modules/core/components/settings/ManagementNameField'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import IdentityService from '@baserow/modules/core/services/identity'
import IdentityLastActiveField from './IdentityLastActiveField'
import IdentityRoleField from './IdentityRoleField'
import IdentityContext from './IdentityContext'
import ManageIdentityModal from './ManageIdentityModal'

export default {
  name: 'IdentitiesTable',
  components: { CrudTable, IdentityContext, ManageIdentityModal },
  props: { workspace: { type: Object, required: true } },
  data() {
    return { focusedIdentityId: null }
  },
  computed: {
    tableLayout() {
      const layout = getManagementTableLayout(this.columns, 'role_uid')
      layout.columnWidths.name = 'max(200px, 40cqw)'
      layout.columnWidths.role_uid = 'auto'
      layout.columnWidths.teams = 'clamp(80px, 10cqw, 120px)'
      layout.columnWidths.last_active = 'clamp(96px, 10cqw, 160px)'
      layout.minTableWidth = '800px'
      return layout
    },
    /**
     * How an identity's row expands into more rows, as given by the first active
     * extension offering it, or null.
     */
    rowExpansion() {
      for (const extension of Object.values(
        this.$registry.getAll('identityExtension')
      )) {
        if (extension.isActive(this.workspace)) {
          const expansion = extension.getRowExpansion({
            workspace: this.workspace,
          })
          if (expansion) {
            return expansion
          }
        }
      }
      return null
    },
    focusedIdentity() {
      // Resolve the selection by ID so realtime updates reach the editor prop.
      return this.$store.getters['identity/get'](this.focusedIdentityId) || null
    },
    canCreate() {
      return this.$hasPermission(
        'identity.create',
        this.workspace,
        this.workspace.id
      )
    },
    canUpdate() {
      return this.$hasPermission(
        'identity.update',
        this.workspace,
        this.workspace.id
      )
    },
    canDelete() {
      return this.$hasPermission(
        'identity.delete',
        this.workspace,
        this.workspace.id
      )
    },
    canManage() {
      return this.canUpdate || this.canDelete
    },
    service() {
      const service = IdentityService(this.$client)
      service.options.urlParams = { workspaceId: this.workspace.id }
      service.fetch = (...args) =>
        this.$store.dispatch('identity/fetchPage', {
          args,
          workspaceId: this.workspace.id,
        })
      return service
    },
    identitiesRevision() {
      return this.$store.getters['identity/getRevision'](this.workspace.id)
    },
    roles() {
      return (this.workspace._?.roles || []).filter(
        (role) =>
          role.isVisible &&
          (!Array.isArray(role.allowedSubjectTypes) ||
            role.allowedSubjectTypes.includes('auth.User'))
      )
    },
    columns() {
      let columns = [
        new CrudTableColumn(
          'name',
          this.$t('identities.name'),
          ManagementNameField,
          true,
          true,
          false,
          {
            avatarComponent: this.$registry.get('subject', 'auth.User')
              .avatarComponent,
          }
        ),
        new CrudTableColumn(
          'role_uid',
          this.$t('identities.workspaceRole'),
          IdentityRoleField,
          true,
          false,
          false,
          {
            roles: this.roles,
            workspace: this.workspace,
          }
        ),
      ]
      for (const extension of Object.values(
        this.$registry.getAll('identityExtension')
      )) {
        if (extension.isActive(this.workspace)) {
          columns = extension.mutateColumns(columns, {
            workspace: this.workspace,
          })
        }
      }
      columns.push(
        new CrudTableColumn(
          'last_active',
          this.$t('identities.lastActive'),
          IdentityLastActiveField,
          true
        )
      )
      if (this.canManage)
        columns.push(
          new CrudTableColumn(null, null, MoreField, false, false, true)
        )
      return columns
    },
  },
  watch: {
    identitiesRevision() {
      this.$refs.table.refresh()
    },
  },
  methods: {
    openContext({ row, event, target }) {
      if (!this.canManage) return
      event?.preventDefault()
      this.focusedIdentityId = row.id
      this.$nextTick(() =>
        this.$refs.context.show(
          target || event.currentTarget,
          'bottom',
          'left',
          4
        )
      )
    },
  },
}
</script>
