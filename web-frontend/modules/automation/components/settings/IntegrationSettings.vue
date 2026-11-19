<template>
  <div>
    <h2 class="box__title">{{ $t('integrationSettings.title') }}</h2>
    <div v-if="state === 'pending'" class="integration-settings__loader" />
    <template v-if="state === 'loaded'">
      <template v-if="integrations && integrations.length > 0">
        <p class="margin-top-3">
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
            :subtitle-error="
              showErrors &&
              getIntegrationType(integration).isInError(integration)
            "
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
              icon="iconoir-community"
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
            :application="automation"
            :integration="integration"
          />
        </div>
      </template>
      <p v-else class="margin-top-3">
        {{ $t('integrationSettings.noIntegrationMessage') }}
      </p>
    </template>
    <PromoteIntegrationModal
      v-if="canPromote"
      ref="promoteModal"
      :application="automation"
      :integration="integrationToPromote"
    />
  </div>
</template>

<script>
import { useStore } from 'vuex'
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import PromoteIntegrationModal from '@baserow/modules/core/components/integrations/PromoteIntegrationModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import {
  integrationSubtitle,
  showIntegrationErrors,
} from '@baserow/modules/core/utils/integration'
import { defineComponent, ref, computed, onMounted, toRefs } from 'vue'

export default defineComponent({
  name: 'IntegrationSettings',
  components: { IntegrationCreateEditModal, PromoteIntegrationModal },
  props: {
    automation: {
      type: Object,
      required: true,
    },
  },

  setup(props) {
    const { automation } = toRefs(props)
    const store = useStore()
    const app = useNuxtApp()
    const state = ref('loaded')

    const integrationTypes = computed(() => {
      return app.$registry.getOrderedList('integration')
    })

    const integrations = computed(() => {
      return store.getters['integration/getIntegrations'](automation.value)
    })

    const showErrors = computed(() => showIntegrationErrors(app))

    const getIntegrationType = (integration) => {
      return app.$registry.get('integration', integration.type)
    }

    const getSubtitle = (integration) => {
      return integrationSubtitle(app, integration)
    }

    // Whether the user can make an integration available to the whole
    // workspace, which creates it there.
    const canPromote = computed(() => {
      const workspace = store.getters['workspace/get'](
        automation.value.workspace.id
      )
      return (
        !!workspace &&
        app.$hasPermission(
          'workspace.create_integration',
          workspace,
          workspace.id
        )
      )
    })

    const promoteModal = ref(null)
    const integrationToPromote = ref(null)

    const showPromoteModal = (integration) => {
      integrationToPromote.value = integration
      promoteModal.value.show()
    }

    const fetchIntegrations = async () => {
      try {
        state.value = 'pending'
        await store.dispatch('integration/fetch', {
          application: automation.value,
        })
        state.value = 'loaded'
      } catch (error) {
        notifyIf(error)
        state.value = 'loaded'
      }
    }

    const deleteIntegration = async (integration) => {
      try {
        await store.dispatch('integration/delete', {
          application: automation.value,
          integrationId: integration.id,
        })
      } catch (error) {
        notifyIf(error)
      }
    }

    onMounted(async () => {
      await fetchIntegrations()
    })

    return {
      state,
      integrationTypes,
      integrations,
      showErrors,
      getIntegrationType,
      getSubtitle,
      deleteIntegration,
      canPromote,
      promoteModal,
      integrationToPromote,
      showPromoteModal,
    }
  },
})
</script>
