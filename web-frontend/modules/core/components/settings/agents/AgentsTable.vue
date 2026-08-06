<template>
  <CrudTable
    ref="table"
    :service="service"
    :columns="columns"
    row-id-key="id"
    @rows-update="count = $event.length"
    @row-context="openContext"
  >
    <template #empty>
      <div class="agents-table__empty">
        <span class="agents-table__empty-icon"
          ><i class="baserow-icon-agent"></i
        ></span>
        <h2>{{ $t('agents.emptyTitle') }}</h2>
        <p>{{ $t('agents.emptyDescription') }}</p>
        <Button
          v-if="canManage"
          type="primary"
          icon="iconoir-plus"
          @click="$refs.createModal.show()"
        >
          {{ $t('agents.create') }}
        </Button>
      </div>
    </template>
    <template #title>{{
      $t('agents.title', { count, workspace: workspace.name })
    }}</template>
    <template #header-right-side>
      <Button
        v-if="canManage"
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
        @edit="$refs.updateModal.show()"
      />
    </template>
  </CrudTable>
  <ManageAgentModal ref="createModal" :workspace="workspace" />
  <ManageAgentModal
    v-if="focusedAgent"
    ref="updateModal"
    :workspace="workspace"
    :agent="focusedAgent"
  />
</template>

<script>
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import AgentService from '@baserow/modules/core/services/agent'
import AgentNameField from './AgentNameField'
import AgentLastActiveField from './AgentLastActiveField'
import AgentRoleField from './AgentRoleField'
import AgentContext from './AgentContext'
import ManageAgentModal from './ManageAgentModal'

export default {
  name: 'AgentsTable',
  components: { CrudTable, AgentContext, ManageAgentModal },
  props: { workspace: { type: Object, required: true } },
  data() {
    return { count: 0, focusedAgent: null }
  },
  computed: {
    canManage() {
      return this.$hasPermission(
        'agent.create',
        this.workspace,
        this.workspace.id
      )
    },
    service() {
      const service = AgentService(this.$client)
      service.options.urlParams = { workspaceId: this.workspace.id }
      service.fetch = (...args) =>
        this.$store.dispatch('agent/fetchPage', { args })
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
          AgentNameField,
          true,
          true
        ),
        new CrudTableColumn(
          'last_active',
          this.$t('agents.lastActive'),
          AgentLastActiveField,
          true
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
      this.focusedAgent = row
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
