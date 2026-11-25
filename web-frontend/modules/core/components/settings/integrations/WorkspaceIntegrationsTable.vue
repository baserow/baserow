<template>
  <div class="workspace-integration-settings">
    <h2 class="workspace-integration-settings__title">
      {{ $t('workspaceIntegrations.title') }}
    </h2>
    <div class="workspace-integration-settings__description">
      <p>{{ $t('workspaceIntegrations.subtitle') }}</p>
      <Button
        v-if="canCreate && sharedApplication && integrations.length"
        type="primary"
        button-type="button"
        icon="iconoir-plus"
        @click="
          $refs.createContext.toggle($event.currentTarget, 'bottom', 'right', 4)
        "
      >
        {{ $t('workspaceIntegrations.create') }}
      </Button>
    </div>
    <div
      v-if="loading"
      class="workspace-integrations-table__status"
      role="status"
    >
      <div
        class="loading"
        :aria-label="$t('workspaceIntegrations.loading')"
      ></div>
    </div>
    <div
      v-else-if="loadFailed"
      class="workspace-integrations-table__status"
      role="alert"
    >
      <p>{{ $t('workspaceIntegrations.loadError') }}</p>
      <Button type="secondary" @click="loadIntegrations">{{
        $t('workspaceIntegrations.retry')
      }}</Button>
    </div>
    <div
      v-else-if="!integrations.length"
      class="workspace-integrations-table__empty"
    >
      <div class="placeholder__icon">
        <i class="iconoir-ev-plug" aria-hidden="true"></i>
      </div>
      <h3>{{ $t('workspaceIntegrations.emptyTitle') }}</h3>
      <p>
        {{
          $t(
            canCreate
              ? 'workspaceIntegrations.emptyDescription'
              : 'workspaceIntegrations.emptyReadOnlyDescription'
          )
        }}
      </p>
      <Button
        v-if="canCreate && sharedApplication"
        type="primary"
        icon="iconoir-plus"
        @click="
          $refs.createContext.toggle($event.currentTarget, 'bottom', 'right', 4)
        "
      >
        {{ $t('workspaceIntegrations.create') }}
      </Button>
    </div>
    <div v-else class="workspace-integrations-table__scroll">
      <table class="workspace-integrations-table">
        <colgroup>
          <col class="workspace-integrations-table__name-column" />
          <col class="workspace-integrations-table__type-column" />
          <col />
          <col
            v-if="canManageAny"
            class="workspace-integrations-table__actions-column"
          />
        </colgroup>
        <thead>
          <tr>
            <th
              v-for="key in ['name', 'type']"
              :key="key"
              scope="col"
              :aria-sort="sortDirection(key)"
            >
              <button
                type="button"
                class="workspace-integrations-table__sort"
                @click="toggleSort(key)"
              >
                {{
                  $t(
                    key === 'name'
                      ? 'workspaceIntegrations.name'
                      : 'workspaceIntegrations.type'
                  )
                }}
                <i
                  v-if="sortDirection(key) !== 'none'"
                  :class="
                    sortDirection(key) === 'ascending'
                      ? 'iconoir-nav-arrow-up'
                      : 'iconoir-nav-arrow-down'
                  "
                  aria-hidden="true"
                ></i>
              </button>
            </th>
            <th scope="col">{{ $t('workspaceIntegrations.details') }}</th>
            <th
              v-if="canManageAny"
              scope="col"
              :aria-label="$t('workspaceIntegrations.actions')"
            ></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="integration in sortedIntegrations"
            :key="integration.id"
            @contextmenu="openContext({ row: integration, event: $event })"
          >
            <td>
              <div class="workspace-integrations-table__identity">
                <WorkspaceIntegrationAvatar
                  :subject="integration"
                  aria-hidden="true"
                />
                <span
                  class="workspace-integrations-table__name"
                  :title="integration.name"
                  >{{ integration.name }}</span
                >
              </div>
            </td>
            <td>{{ getTypeName(integration) }}</td>
            <td><WorkspaceIntegrationDetailsField :row="integration" /></td>
            <td v-if="canManageAny">
              <button
                v-if="canManage(integration)"
                type="button"
                class="workspace-integrations-table__more"
                :aria-label="$t('workspaceIntegrations.actions')"
                aria-haspopup="menu"
                @click="openContext({ row: integration, event: $event })"
              >
                <i class="baserow-icon-more-vertical" aria-hidden="true"></i>
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <WorkspaceIntegrationContext
      v-if="focusedIntegration"
      ref="context"
      :can-update="canUpdate(focusedIntegration)"
      :can-delete="canDelete(focusedIntegration)"
      @edit="$refs.updateModal.show()"
      @delete="confirmDelete"
    />
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
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import ConfirmModal from '@baserow/modules/core/components/modals/ConfirmModal'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import WorkspaceIntegrationAvatar from './WorkspaceIntegrationAvatar'
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
    WorkspaceIntegrationAvatar,
    WorkspaceIntegrationDetailsField,
    ConfirmModal,
    IntegrationCreateEditModal,
    WorkspaceIntegrationContext,
    WorkspaceIntegrationCreateContext,
  },
  props: { workspace: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      loadFailed: false,
      sorts: [],
      focusedIntegrationId: null,
      // Only the name: the registry's type object would be made reactive here,
      // along with the form component it returns.
      createIntegrationTypeName: null,
      integrationToDelete: null,
      deleting: false,
    }
  },
  computed: {
    createIntegrationType() {
      return this.createIntegrationTypeName
        ? this.$registry.get('integration', this.createIntegrationTypeName)
        : null
    },
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
    sortedIntegrations() {
      return [...this.integrations].sort((a, b) => {
        for (const { key, direction } of this.sorts) {
          const valueA = key === 'type' ? this.getTypeName(a) : a.name
          const valueB = key === 'type' ? this.getTypeName(b) : b.name
          const order = valueA.localeCompare(valueB)
          if (order) return direction === 'ascending' ? order : -order
        }
        return 0
      })
    },
    deleteMessage() {
      return this.$t('workspaceIntegrations.deleteMessage', {
        name: this.integrationToDelete?.name || '',
      })
    },
  },
  mounted() {
    this.loadIntegrations()
  },
  methods: {
    /** Load the shared integrations once; expose failures so they can be retried. */
    async loadIntegrations() {
      this.loading = true
      this.loadFailed = false
      try {
        const application = await this.$store.dispatch(
          'application/fetchSharedApplication',
          this.workspace
        )
        if (application) {
          const integrations = await this.$store.dispatch('integration/fetch', {
            application,
          })
          this.loadFailed = integrations === null
        }
      } catch {
        this.loadFailed = true
      } finally {
        this.loading = false
      }
    },
    toggleSort(key) {
      const sort = this.sorts.find((sort) => sort.key === key)
      if (!sort) this.sorts.push({ key, direction: 'ascending' })
      else if (sort.direction === 'ascending') sort.direction = 'descending'
      else this.sorts = this.sorts.filter((sort) => sort.key !== key)
    },
    sortDirection(key) {
      return this.sorts.find((sort) => sort.key === key)?.direction || 'none'
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
      this.createIntegrationTypeName = integrationType.type
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
