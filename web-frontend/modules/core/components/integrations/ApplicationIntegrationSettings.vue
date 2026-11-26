<template>
  <div>
    <h2 class="box__title">{{ $t('integrationSettings.title') }}</h2>
    <template v-if="workspaceIntegrations.length > 0">
      <h3 class="integration-settings__section-title">
        {{ $t('applicationIntegrationSettings.workspaceIntegrations') }}
      </h3>
      <p class="integration-settings__section-description">
        {{ $t('applicationIntegrationSettings.workspaceDescription') }}
        <ButtonText
          v-if="canOpenWorkspaceSettings"
          button-type="button"
          @click="$refs.workspaceSettings.show('integrations')"
        >
          {{ $t('applicationIntegrationSettings.openWorkspaceSettings') }}
        </ButtonText>
      </p>
      <div
        v-for="integration in workspaceIntegrations"
        :key="integration.id"
        class="integration-settings__integration"
      >
        <Presentation
          :image="getIntegrationType(integration).image"
          :icon="getIntegrationType(integration).iconClass"
          :title="integration.name"
          :subtitle="getWorkspaceSubtitle(integration)"
          :subtitle-error="isInError(integration)"
          :rounded-icon="false"
          avatar-color="transparent"
          style="flex: 1"
        />
      </div>
      <h3 class="integration-settings__section-title">
        {{ $t('applicationIntegrationSettings.applicationIntegrations') }}
      </h3>
    </template>
    <template v-if="integrations.length > 0">
      <p class="integration-settings__section-description">
        {{ $t('integrationSettings.integrationMessage') }}
      </p>
      <div
        v-for="integration in integrations"
        :key="integration.id"
        class="integration-settings__integration"
      >
        <Presentation
          :image="getIntegrationType(integration).image"
          :icon="getIntegrationType(integration).iconClass"
          :title="integration.name"
          :subtitle="getSubtitle(integration)"
          :subtitle-error="isInError(integration)"
          :rounded-icon="false"
          avatar-color="transparent"
          style="flex: 1"
        />
        <div class="integration-settings__integration-actions">
          <ButtonIcon
            icon="iconoir-edit"
            @click="
              $refs[`IntegrationCreateEditModal_${integration.id}`][0].show()
            "
          />
          <ButtonIcon
            v-if="canPromote"
            v-tooltip="$t('promoteIntegration.action')"
            icon="iconoir-share-android"
            @click="showPromoteModal(integration)"
          />
          <ButtonIcon
            icon="iconoir-bin"
            @click="deleteIntegration(integration)"
          />
        </div>
        <IntegrationCreateEditModal
          :ref="`IntegrationCreateEditModal_${integration.id}`"
          :data-integration-id="integration.id"
          :application="application"
          :integration="integration"
        />
      </div>
    </template>
    <p v-else class="integration-settings__section-description">
      {{ $t('integrationSettings.noIntegrationMessage') }}
    </p>
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
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  integrationSubtitle,
  showIntegrationErrors,
} from '@baserow/modules/core/utils/integration'

/**
 * The integrations settings of an application: the workspace integrations it
 * can use, read-only since they're managed in the workspace settings, then its
 * own, which can be edited, made available to the whole workspace and deleted.
 *
 * Options API, as in the builder's `IntegrationSettings` it was moved from.
 */
export default {
  name: 'ApplicationIntegrationSettings',
  components: {
    IntegrationCreateEditModal,
    PromoteIntegrationModal,
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
    return { integrationToPromote: null }
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
    showErrors() {
      return showIntegrationErrors(this)
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
    isInError(integration) {
      return (
        this.showErrors &&
        this.getIntegrationType(integration).isInError(integration)
      )
    },
    getSubtitle(integration) {
      return integrationSubtitle(this, integration)
    },
    /**
     * Why the workspace integration is in error, otherwise who or what it runs
     * as in the applications of the workspace, or its summary.
     */
    getWorkspaceSubtitle(integration) {
      const integrationType = this.getIntegrationType(integration)
      return (
        (this.showErrors && integrationType.getErrorMessage(integration)) ||
        integrationType.getWorkspaceHint(integration) ||
        integrationType.getSummary(integration)
      )
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
