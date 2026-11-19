<template>
  <CrudTable
    v-bind="tableLayout"
    ref="table"
    class="management-table"
    :service="service"
    :columns="columns"
    row-id-key="id"
    :search-placeholder="$t('workspaceIntegrations.search')"
    @row-context="openContext"
  >
    <template #title="{ count }">{{
      $t('workspaceIntegrations.title', { count, workspace: workspace.name })
    }}</template>
    <template #subtitle>{{ $t('workspaceIntegrations.subtitle') }}</template>
    <template #empty>
      <div class="placeholder">
        <div class="placeholder__icon">
          <i class="iconoir-ev-plug" aria-hidden="true"></i>
        </div>
        <h2 class="placeholder__header">
          {{ $t('workspaceIntegrations.emptyTitle') }}
        </h2>
        <p class="placeholder__content">
          {{ $t('workspaceIntegrations.emptyDescription') }}
        </p>
      </div>
    </template>
    <template #primary-action>
      <Button
        v-if="canCreate && sharedApplication"
        type="primary"
        size="large"
        icon="iconoir-plus"
        @click="
          $refs.createContext.toggle($event.currentTarget, 'bottom', 'right', 4)
        "
      >
        {{ $t('workspaceIntegrations.create') }}
      </Button>
    </template>
    <template #menus>
      <WorkspaceIntegrationContext
        v-if="focusedIntegration"
        ref="context"
        :can-update="canUpdate(focusedIntegration)"
        :can-delete="canDelete(focusedIntegration)"
        @edit="$refs.updateModal.show()"
        @delete="confirmDelete"
      />
    </template>
  </CrudTable>
  <WorkspaceIntegrationCreateContext
    v-if="canCreate"
    ref="createContext"
    @select="showCreateModal"
  />
  <template v-if="sharedApplication">
    <IntegrationCreateEditModal
      v-if="createIntegrationType"
      ref="createModal"
      :application="sharedApplication"
      :integration-type="createIntegrationType"
      create
    />
    <IntegrationCreateEditModal
      v-if="focusedIntegration && canUpdate(focusedIntegration)"
      ref="updateModal"
      :application="sharedApplication"
      :integration="focusedIntegration"
    />
  </template>
  <ConfirmModal
    ref="deleteModal"
    danger
    :title="$t('workspaceIntegrations.deleteTitle')"
    :message="deleteMessage"
    :confirm-label="$t('workspaceIntegrations.delete')"
    :loading="deleting"
    @confirm="deleteIntegration"
  />
</template>

<script>
import { getManagementTableLayout } from '@baserow/modules/core/utils/managementTable'
import { notifyIf } from '@baserow/modules/core/utils/error'
import CrudTable from '@baserow/modules/core/components/crudTable/CrudTable'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import MoreField from '@baserow/modules/core/components/crudTable/fields/MoreField'
import ManagementNameField from '@baserow/modules/core/components/settings/ManagementNameField'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import WorkspaceIntegrationAvatar from './WorkspaceIntegrationAvatar'
import WorkspaceIntegrationTypeField from './WorkspaceIntegrationTypeField'
import WorkspaceIntegrationDetailsField from './WorkspaceIntegrationDetailsField'
import WorkspaceIntegrationContext from './WorkspaceIntegrationContext'
import WorkspaceIntegrationCreateContext from './WorkspaceIntegrationCreateContext'

/**
 * The integrations of the workspace's shared application, which every application
 * in the workspace can use. They're kept in the integration store like those of
 * any application, so the store actions and the realtime events keep this list up
 * to date, and the table only fetches them once.
 */
export default {
  name: 'WorkspaceIntegrationsTable',
  components: {
    CrudTable,
    ConfirmModal,
    IntegrationCreateEditModal,
    WorkspaceIntegrationContext,
    WorkspaceIntegrationCreateContext,
  },
  props: { workspace: { type: Object, required: true } },
  data() {
    return {
      // The first fetch of the workspace integrations, shared by the table
      // fetches that happen while it runs.
      loadingIntegrations: null,
      focusedIntegrationId: null,
      createIntegrationType: null,
      integrationToDelete: null,
      deleting: false,
    }
  },
  computed: {
    sharedApplication() {
      return this.$store.getters['application/getSharedApplication'](
        this.workspace
      )
    },
    integrations() {
      return this.sharedApplication
        ? this.$store.getters['integration/getIntegrations'](
            this.sharedApplication
          )
        : []
    },
    integrationsGeneration() {
      return this.sharedApplication
        ? this.$store.getters['integration/getGeneration'](
            this.sharedApplication
          )
        : 0
    },
    focusedIntegration() {
      // Resolved by id, so realtime updates reach the edit modal.
      return (
        (this.sharedApplication &&
          this.$store.getters['integration/getIntegrationById'](
            this.sharedApplication,
            this.focusedIntegrationId
          )) ||
        null
      )
    },
    canCreate() {
      return this.$hasPermission(
        'workspace.create_integration',
        this.workspace,
        this.workspace.id
      )
    },
    canManageAny() {
      return this.integrations.some(this.canManage)
    },
    service() {
      return {
        options: { isPaginated: false },
        fetch: async (baseUrl, page, searchQuery, sorts) => {
          await this.loadIntegrations()
          return { data: this.listIntegrations(searchQuery, sorts) }
        },
      }
    },
    columns() {
      const columns = [
        new CrudTableColumn(
          'name',
          this.$t('workspaceIntegrations.name'),
          ManagementNameField,
          true,
          true,
          false,
          { avatarComponent: WorkspaceIntegrationAvatar }
        ),
        new CrudTableColumn(
          'type',
          this.$t('workspaceIntegrations.type'),
          WorkspaceIntegrationTypeField,
          true
        ),
        new CrudTableColumn(
          'details',
          this.$t('workspaceIntegrations.details'),
          WorkspaceIntegrationDetailsField
        ),
      ]
      if (this.canManageAny) {
        columns.push(
          new CrudTableColumn(null, null, MoreField, false, false, true)
        )
      }
      return columns
    },
    tableLayout() {
      const layout = getManagementTableLayout(this.columns, 'type')
      layout.columnWidths.type = 'clamp(120px, 15cqw, 200px)'
      return layout
    },
    deleteMessage() {
      return this.$t('workspaceIntegrations.deleteMessage', {
        name: this.integrationToDelete?.name || '',
      })
    },
  },
  watch: {
    integrationsGeneration() {
      this.$refs.table?.refresh({ silent: true })
    },
  },
  methods: {
    /**
     * Fetches the shared application, if the store doesn't have it yet, and its
     * integrations. Only the first table fetch waits for it, a failed one is
     * tried again by the next.
     */
    loadIntegrations() {
      if (!this.loadingIntegrations) {
        this.loadingIntegrations = this.fetchIntegrations().catch((error) => {
          this.loadingIntegrations = null
          throw error
        })
      }
      return this.loadingIntegrations
    },
    async fetchIntegrations() {
      const application = await this.$store.dispatch(
        'application/fetchSharedApplication',
        this.workspace
      )
      if (application) {
        await this.$store.dispatch('integration/fetch', { application })
      }
    },
    /**
     * The workspace integrations whose name or type contains the search, in the
     * order of the sorted columns, or in their own order when none is sorted.
     */
    listIntegrations(searchQuery, sorts) {
      const search = (searchQuery || '').trim().toLowerCase()
      const integrations = this.integrations.filter(
        (integration) =>
          !search ||
          [integration.name, this.getTypeName(integration)].some((value) =>
            value.toLowerCase().includes(search)
          )
      )
      // A first click on a column sorts it `desc`, which the paginated tables
      // send to the backend as A to Z (`crudTable/baseService.js`), so `desc` is
      // A to Z here too.
      return integrations.sort((a, b) => {
        for (const { key, direction } of sorts) {
          const order = this.getSortValue(a, key).localeCompare(
            this.getSortValue(b, key)
          )
          if (order !== 0) {
            return direction === 'desc' ? order : -order
          }
        }
        return 0
      })
    },
    getSortValue(integration, key) {
      return key === 'type'
        ? this.getTypeName(integration)
        : String(integration[key] ?? '')
    },
    getTypeName(integration) {
      return this.$registry.get('integration', integration.type).name
    },
    canUpdate(integration) {
      return this.$hasPermission(
        'workspace.integration.update',
        integration,
        this.workspace.id
      )
    },
    canDelete(integration) {
      return this.$hasPermission(
        'workspace.integration.delete',
        integration,
        this.workspace.id
      )
    },
    canManage(integration) {
      return this.canUpdate(integration) || this.canDelete(integration)
    },
    openContext({ row, event, target }) {
      if (!this.canManage(row)) return
      event?.preventDefault()
      this.focusedIntegrationId = row.id
      this.$nextTick(() =>
        this.$refs.context.show(
          target || event.currentTarget,
          'bottom',
          'left',
          4
        )
      )
    },
    async showCreateModal(integrationType) {
      this.createIntegrationType = integrationType
      await this.$nextTick()
      this.$refs.createModal.show()
    },
    confirmDelete() {
      this.integrationToDelete = this.focusedIntegration
      this.$refs.deleteModal.show()
    },
    async deleteIntegration() {
      this.deleting = true
      try {
        await this.$store.dispatch('integration/delete', {
          application: this.sharedApplication,
          integrationId: this.integrationToDelete.id,
        })
        this.$refs.deleteModal.hide()
      } catch (error) {
        notifyIf(error, 'integration')
      }
      this.deleting = false
    },
  },
}
</script>
