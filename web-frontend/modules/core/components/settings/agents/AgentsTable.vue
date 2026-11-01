<template>
  <CrudTable
    v-bind="tableLayout"
    ref="table"
    class="management-table management-table--agents"
    :service="service"
    :columns="columns"
    row-id-key="id"
    :search-placeholder="$t('agents.search')"
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
      $t('agents.title', { count, workspace: workspace.name })
    }}</template>
    <template #empty>
      <div class="placeholder">
        <div class="placeholder__icon">
          <i class="baserow-icon-agent" aria-hidden="true"></i>
        </div>
        <h2 class="placeholder__header">{{ $t('agents.emptyTitle') }}</h2>
        <p class="placeholder__content">{{ $t('agents.emptyDescription') }}</p>
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
        {{ $t('agents.create') }}
      </Button>
    </template>
    <template #menus>
      <AgentContext
        v-if="focusedAgent && canManage"
        ref="context"
        :agent="focusedAgent"
        :can-update="canUpdate"
        :can-delete="canDelete"
        @edit="$refs.updateModal.show()"
      />
    </template>
  </CrudTable>
  <ManageAgentModal ref="createModal" :workspace="workspace" />
  <ManageAgentModal
    v-if="focusedAgent && canUpdate"
    ref="updateModal"
    :workspace="workspace"
    :agent="focusedAgent"
  />
</template>

<script>
import { getManagementTableLayout } from '@baserow/modules/core/utils/managementTable'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import ManagementNameField from '@baserow/modules/core/components/settings/ManagementNameField'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import AgentService from '@baserow/modules/core/services/agent'
import AgentLastActiveField from './AgentLastActiveField'
import AgentRoleField from './AgentRoleField'
import AgentContext from './AgentContext'
import ManageAgentModal from './ManageAgentModal'

export default {
  name: 'AgentsTable',
  components: { CrudTable, AgentContext, ManageAgentModal },
  props: { workspace: { type: Object, required: true } },
  data() {
    return { focusedAgentId: null }
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
     * How an agent's row expands into more rows, as given by the first active
     * extension offering it, or null.
     */
    rowExpansion() {
      for (const extension of Object.values(
        this.$registry.getAll('agentExtension')
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
    focusedAgent() {
      // Resolve the selection by ID so realtime updates reach the editor prop.
      return this.$store.getters['agent/get'](this.focusedAgentId) || null
    },
    canCreate() {
      return this.$hasPermission(
        'agent.create',
        this.workspace,
        this.workspace.id
      )
    },
    canUpdate() {
      return this.$hasPermission(
        'agent.update',
        this.workspace,
        this.workspace.id
      )
    },
    canDelete() {
      return this.$hasPermission(
        'agent.delete',
        this.workspace,
        this.workspace.id
      )
    },
    canManage() {
      return this.canUpdate || this.canDelete
    },
    service() {
      const service = AgentService(this.$client)
      service.options.urlParams = { workspaceId: this.workspace.id }
      service.fetch = (...args) =>
        this.$store.dispatch('agent/fetchPage', {
          args,
          workspaceId: this.workspace.id,
        })
      return service
    },
    agentsRevision() {
      return this.$store.getters['agent/getRevision'](this.workspace.id)
    },
    roles() {
      return (this.workspace._?.roles || []).filter(
        (role) =>
          role.isVisible &&
          (!Array.isArray(role.allowedSubjectTypes) ||
            role.allowedSubjectTypes.includes('core.Agent'))
      )
    },
    columns() {
      let columns = [
        new CrudTableColumn(
          'name',
          this.$t('agents.name'),
          ManagementNameField,
          true,
          true,
          false,
          {
            avatarComponent: this.$registry.get('subject', 'core.Agent')
              .avatarComponent,
          }
        ),
        new CrudTableColumn(
          'role_uid',
          this.$t('agents.workspaceRole'),
          AgentRoleField,
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
        this.$registry.getAll('agentExtension')
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
          this.$t('agents.lastActive'),
          AgentLastActiveField,
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
    agentsRevision() {
      this.$refs.table.refresh()
    },
  },
  methods: {
    openContext({ row, event, target }) {
      if (!this.canManage) return
      event?.preventDefault()
      this.focusedAgentId = row.id
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
