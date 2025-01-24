<template>
  <Modal>
    <h2 class="box__title">
      {{
        $t('updateSettingsAuthProviderModal.title', {
          name: getProviderName(),
        })
      }}
    </h2>
    <div>
      <component
        :is="getProviderAdminSettingsFormComponent()"
        ref="providerSettingsForm"
        :auth-providers="appAuthProviderPerTypes"
        :auth-provider="authProvider"
        :default-values="authProvider"
        :auth-provider-type="authProviderType"
        @submit="onSettingsUpdated"
      >
        <div class="actions">
          <ul class="action__links">
            <li>
              <a @click="$emit('cancel')">{{ $t('action.cancel') }}</a>
            </li>
          </ul>

          <Button type="primary" :disabled="loading" :loading="loading">
            {{ $t('action.save') }}
          </Button>
        </div>
      </component>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import { notifyIf } from '@baserow/modules/core/utils/error'

export default {
  name: 'UpdateSettingsAuthProviderModal',
  mixins: [modal],
  props: {
    authProvider: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  computed: {
    authProviderType() {
      return this.$registry.get('authProvider', this.authProvider.type)
    },
    authProviders() {
      return this.$store.getters['authProviderAdmin/getAll']
    },
    appAuthProviderPerTypes() {
      return Object.fromEntries(
        this.$registry
          .getOrderedList('authProvider')
          .map((authProviderType) => [
            authProviderType.getType(),
            this.authProviders[authProviderType.getType()].authProviders,
          ])
      )
    },
  },
  methods: {
    getProviderAdminSettingsFormComponent() {
      return this.authProviderType.getAdminSettingsFormComponent()
    },
    getProviderName() {
      return this.authProviderType.getProviderName(this.authProvider)
    },
    async onSettingsUpdated(values) {
      this.loading = true
      try {
        await this.$store.dispatch('authProviderAdmin/update', {
          authProvider: this.authProvider,
          values,
        })
        this.$emit('settings-updated')
      } catch (error) {
        if (!this.$refs.providerSettingsForm.handleServerError(error)) {
          notifyIf(error, 'settings')
        }
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
