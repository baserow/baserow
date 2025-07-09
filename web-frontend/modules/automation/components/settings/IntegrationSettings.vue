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
            :subtitle="getIntegrationType(integration).getSummary(integration)"
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
  </div>
</template>

<script>
import IntegrationCreateEditModal from '@baserow/modules/core/components/integrations/IntegrationCreateEditModal'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { defineComponent, ref, computed, onMounted, toRefs } from 'vue'
import { useStore, useContext } from '@nuxtjs/composition-api'

export default defineComponent({
  name: 'IntegrationSettings',
  components: { IntegrationCreateEditModal },
  props: {
    automation: {
      type: Object,
      required: true,
    },
  },

  setup(props) {
    const { automation } = toRefs(props)
    const store = useStore()
    const { app } = useContext()
    const state = ref('loaded')

    const integrationTypes = computed(() => {
      return app.$registry.getOrderedList('integration')
    })

    const integrations = computed(() => {
      return store.getters['integration/getIntegrations'](automation.value)
    })

    const getIntegrationType = (integration) => {
      return app.$registry.get('integration', integration.type)
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
      getIntegrationType,
      deleteIntegration,
    }
  },
})
</script>
