<template>
  <Modal>
    <h2 class="box__title">
      {{
        $t('createSettingsAuthProviderModal.title', {
          type: authProviderType.getName(),
        })
      }}
    </h2>
    <div>
      <component
        :is="getProviderAdminSettingsFormComponent()"
        ref="providerSettingsForm"
        :auth-providers="appAuthProviderPerTypes"
        :auth-provider-type="authProviderType"
        @submit="create($event)"
      >
        <div class="actions">
          <ul class="action__links">
            <li>
              <a @click="$emit('cancel')">{{ $t('action.cancel') }}</a>
            </li>
          </ul>
          <Button type="primary" :disabled="loading" :loading="loading">
            {{ $t('action.create') }}
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
  name: 'CreateAuthProviderModal',
  mixins: [modal],
  props: {
    authProviderType: {
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
    async create(values) {
      this.loading = true
      try {
        await this.$store.dispatch('authProviderAdmin/create', {
          type: this.authProviderType.getType(),
          values,
        })
        this.$emit('created')
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
