<template>
  <div>
    <h2 class="box__title">{{ $t('integrationSettings.title') }}</h2>
    <p class="integration-settings__description">
      {{ $t('applicationIntegrationSettings.description') }}
    </p>
    <p
      v-if="!integrations.length && !workspaceIntegrations.length"
      class="integration-settings__description"
    >
      {{ $t('integrationSettings.noIntegrationMessage') }}
    </p>
    <div v-else class="workspace-integrations-table__scroll">
      <table class="workspace-integrations-table">
        <colgroup>
          <col class="workspace-integrations-table__name-column" />
          <col class="workspace-integrations-table__type-column" />
          <col />
          <col class="workspace-integrations-table__actions-column" />
        </colgroup>
        <thead>
          <tr>
            <th scope="col">{{ $t('workspaceIntegrations.name') }}</th>
            <th scope="col">{{ $t('workspaceIntegrations.type') }}</th>
            <th scope="col">{{ $t('workspaceIntegrations.details') }}</th>
            <th
              scope="col"
              :aria-label="$t('workspaceIntegrations.actions')"
            ></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-if="workspaceIntegrations.length"
            class="integration-settings__group"
          >
            <th colspan="4" scope="colgroup">
              <div class="integration-settings__group-content">
                <span class="integration-settings__group-title">
                  {{
                    $t('applicationIntegrationSettings.applicationIntegrations')
                  }}
                </span>
              </div>
            </th>
          </tr>
          <tr
            v-for="integration in integrations"
            :key="integration.id"
            class="integration-settings__integration"
            @contextmenu="openContext(integration, $event)"
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
            <td>{{ getIntegrationType(integration).name }}</td>
            <td><WorkspaceIntegrationDetailsField :row="integration" /></td>
            <td>
              <button
                type="button"
                class="workspace-integrations-table__more"
                :aria-label="$t('workspaceIntegrations.actions')"
                aria-haspopup="menu"
                @click="openContext(integration, $event)"
              >
                <i class="baserow-icon-more-vertical" aria-hidden="true"></i>
              </button>
            </td>
          </tr>
          <tr v-if="!integrations.length">
            <td colspan="4" class="integration-settings__empty">
              {{ $t('integrationSettings.noIntegrationMessage') }}
            </td>
          </tr>
        </tbody>
        <tbody v-if="workspaceIntegrations.length">
          <tr class="integration-settings__group">
            <th colspan="4" scope="colgroup">
              <div class="integration-settings__group-content">
                <span class="integration-settings__group-title">
                  {{
                    $t('applicationIntegrationSettings.workspaceIntegrations')
                  }}
                </span>
                <button
                  v-if="canOpenWorkspaceSettings"
                  type="button"
                  class="integration-settings__link"
                  @click="openWorkspaceSettings"
                >
                  {{ $t('applicationIntegrationSettings.manageInWorkspace') }}
                  <i class="iconoir-nav-arrow-right" aria-hidden="true"></i>
                </button>
              </div>
            </th>
          </tr>
          <tr
            v-for="integration in workspaceIntegrations"
            :key="integration.id"
            class="integration-settings__integration"
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
            <td>{{ getIntegrationType(integration).name }}</td>
            <td><WorkspaceIntegrationDetailsField :row="integration" /></td>
            <td></td>
          </tr>
        </tbody>
      </table>
    </div>
    <div
      v-if="canPromote && integrations.length && !workspaceIntegrations.length"
      class="integration-settings__hint"
    >
      <i
        class="integration-settings__hint-icon iconoir-share-android"
        aria-hidden="true"
      ></i>
      <i18n-t
        scope="global"
        keypath="applicationIntegrationSettings.shareHint"
        tag="p"
      >
        <template #workspace>
          <button
            v-if="canOpenWorkspaceSettings"
            type="button"
            class="integration-settings__link"
            @click="openWorkspaceSettings"
          >
            {{ $t('applicationIntegrationSettings.shareHintWorkspace') }}
          </button>
          <template v-else>{{
            $t('applicationIntegrationSettings.shareHintWorkspace')
          }}</template>
        </template>
      </i18n-t>
    </div>
    <WorkspaceIntegrationContext
      v-if="focusedIntegration"
      ref="context"
      can-update
      can-delete
      :can-promote="canPromote"
      @edit="$refs.editModal.show()"
      @promote="showPromoteModal(focusedIntegration)"
      @delete="deleteIntegration(focusedIntegration)"
    />
    <IntegrationCreateEditModal
      v-if="focusedIntegration"
      ref="editModal"
      :application="application"
      :integration="focusedIntegration"
    />
    <WorkspaceSettingsModal
      v-if="canOpenWorkspaceSettings"
      ref="workspaceSettings"
      :workspace="workspace"
    />
    <PromoteIntegrationModal
      v-if="canPromote"
      ref="promoteModal"
      :application="application"
      :integration="integrationToPromote"
    />
  </div>
</template>

<script>
import WorkspaceSettingsModal from '@baserow/modules/core/components/workspace/WorkspaceSettingsModal'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import PromoteIntegrationModal from '@baserow/modules/core/components/integrations/PromoteIntegrationModal'
import WorkspaceIntegrationAvatar from '@baserow/modules/core/components/settings/integrations/WorkspaceIntegrationAvatar'
import WorkspaceIntegrationContext from '@baserow/modules/core/components/settings/integrations/WorkspaceIntegrationContext'
import WorkspaceIntegrationDetailsField from '@baserow/modules/core/components/settings/integrations/WorkspaceIntegrationDetailsField'
import { notifyIf } from '@baserow/modules/core/utils/error'

/**
 * The integrations settings of an application, in one table that looks like the
 * workspace integrations table: its own first, since the settings are about this
 * application, which can be edited, made available to the whole workspace and
 * deleted from their menu, then the workspace integrations it can use,
 * read-only since they're managed in the workspace settings.
 *
 * Options API, as in the builder's `IntegrationSettings` it was moved from.
 */
export default {
  name: 'ApplicationIntegrationSettings',
  components: {
    IntegrationCreateEditModal,
    PromoteIntegrationModal,
    WorkspaceIntegrationAvatar,
    WorkspaceIntegrationContext,
    WorkspaceIntegrationDetailsField,
    WorkspaceSettingsModal,
  },
  props: {
    application: {
      type: Object,
      required: true,
    },
  },
  emits: ['deleted'],
  data() {
    return { focusedIntegrationId: null, integrationToPromote: null }
  },
  computed: {
    workspace() {
      return this.$store.getters['workspace/get'](this.application.workspace.id)
    },
    /**
     * Whether the user can make an integration available to the whole
     * workspace, which creates it there.
     */
    canPromote() {
      return (
        !!this.workspace &&
        this.$hasPermission(
          'workspace.create_integration',
          this.workspace,
          this.workspace.id
        )
      )
    },
    /**
     * Whether the user can open the workspace settings page that lists the
     * workspace integrations.
     */
    canOpenWorkspaceSettings() {
      return (
        !!this.workspace &&
        this.$hasPermission(
          'workspace.list_integrations',
          this.workspace,
          this.workspace.id
        )
      )
    },
    integrations() {
      return this.$store.getters['integration/getIntegrations'](
        this.application
      )
    },
    workspaceIntegrations() {
      return this.$store.getters['integration/getWorkspaceIntegrations'](
        this.application
      )
    },
    focusedIntegration() {
      // Resolved by id, so realtime updates reach the edit modal, and a
      // deleted or promoted integration closes its menu.
      return (
        this.$store.getters['integration/getIntegrationById'](
          this.application,
          this.focusedIntegrationId
        ) || null
      )
    },
  },
  async mounted() {
    try {
      // Both lists, so the workspace ones show what they can reach now too.
      await this.$store.dispatch('integration/fetchUsable', {
        application: this.application,
      })
    } catch (error) {
      notifyIf(error)
    }
  },
  methods: {
    getIntegrationType(integration) {
      return this.$registry.get('integration', integration.type)
    },
    openWorkspaceSettings() {
      this.$refs.workspaceSettings.show('integrations')
    },
    openContext(integration, event) {
      event.preventDefault()
      const target = event.currentTarget
      this.focusedIntegrationId = integration.id
      this.$nextTick(() => this.$refs.context.show(target, 'bottom', 'left', 4))
    },
    showPromoteModal(integration) {
      this.integrationToPromote = integration
      this.$refs.promoteModal.show()
    },
    async deleteIntegration(integration) {
      try {
        await this.$store.dispatch('integration/delete', {
          application: this.application,
          integrationId: integration.id,
        })
        this.$emit('deleted', integration)
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
