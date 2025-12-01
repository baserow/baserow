<template>
  <div>
    <h2 class="box__title">{{ $t('integrationSettings.title') }}</h2>
    <div v-if="state === 'pending'" class="integration-settings__loader" />
    <template v-if="state === 'loaded'">
      <template v-if="integrations.length > 0">
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
            :application="builder"
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
import { mapActions } from 'vuex'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'IntegrationSettings',
  components: { IntegrationCreateEditModal },
  props: {
    builder: {
      type: Object,
      required: true,
    },
  },
  data() {
    return { state: 'loaded' }
  },
  computed: {
    integrationTypes() {
      return this.$registry.getOrderedList('integration')
    },
    integrations() {
      return this.$store.getters['integration/getIntegrations'](this.builder)
    },
  },
  async mounted() {
    try {
      await Promise.all([
        this.actionFetchIntegrations({
          application: this.builder,
        }),
      ])
    } catch (error) {
      notifyIf(error)
    }
  },
  methods: {
    ...mapActions({
      actionFetchIntegrations: 'integration/fetch',
      actionDeleteIntegration: 'integration/delete',
    }),
    getIntegrationType(integration) {
      return this.$registry.get('integration', integration.type)
    },
    async deleteIntegration(integration) {
      try {
        await this.actionDeleteIntegration({
          application: this.builder,
          integrationId: integration.id,
        })
      } catch (error) {
        notifyIf(error)
      }
    },
  },
}
</script>
