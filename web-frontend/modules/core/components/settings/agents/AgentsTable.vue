<template>
  <CrudTable
    ref="table"
    :service="service"
    :columns="columns"
    row-id-key="id"
    @total-count-update="count = $event"
    @row-context="openContext"
  >
    <template #title>{{
      $t('agents.title', { count, workspace: workspace.name })
    }}</template>
    <template #header-right-side>
      <Button
        v-if="canCreate"
        type="primary"
        size="large"
        class="margin-left-2"
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
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import SimpleField from '@baserow/modules/core/components/crudTable/fields/SimpleField'
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
    return { count: 0, focusedAgentId: null }
  },
  computed: {
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
          SimpleField,
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
