<template>
  <Modal ref="modal" small @show="hideError()">
    <template v-if="integration">
      <h2 class="box__title">
        {{ $t('promoteIntegration.title', { name: integration.name }) }}
      </h2>
      <p>
        {{ $t('promoteIntegration.description', { workspace: workspaceName }) }}
      </p>
      <p>{{ $t('promoteIntegration.keepsWorking') }}</p>
      <p v-if="promotionHint">{{ promotionHint }}</p>
      <Error :error="error"></Error>
      <div class="actions margin-bottom-0">
        <ul class="action__links">
          <li>
            <a @click="hide()">{{ $t('action.cancel') }}</a>
          </li>
        </ul>
        <Button
          type="primary"
          :loading="loading"
          :disabled="loading"
          @click="promote()"
        >
          {{ $t('promoteIntegration.confirm') }}
        </Button>
      </div>
    </template>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'

/**
 * Asks an admin to confirm that an app-level integration is made available to the
 * whole workspace, then moves it to the workspace's shared application. The
 * application's services and user sources keep using it, since an application
 * can use the workspace integrations too.
 *
 * Options API like `IntegrationCreateEditModal`: the `modal` and `error` mixins
 * give it `show`, `hide` and the error box.
 */
export default {
  name: 'PromoteIntegrationModal',
  mixins: [modal, error],
  props: {
    // The application that owns the integration.
    application: {
      type: Object,
      required: true,
    },
    // The app-level integration to promote, null until one is picked.
    integration: {
      type: Object,
      required: false,
      default: null,
    },
  },
  data() {
    return { loading: false }
  },
  computed: {
    workspaceName() {
      const { id, name } = this.application.workspace
      return this.$store.getters['workspace/get'](id)?.name || name
    },
    promotionHint() {
      if (!this.integration) {
        return null
      }
      return this.$registry
        .get('integration', this.integration.type)
        .getPromotionHint(this.integration)
    },
  },
  methods: {
    async promote() {
      const integration = this.integration
      this.loading = true
      this.hideError()
      try {
        const sharedApplication = await this.$store.dispatch(
          'application/fetchSharedApplication',
          this.application.workspace
        )
        await this.$store.dispatch('integration/moveToApplication', {
          application: this.application,
          applicationDest: sharedApplication,
          integrationId: integration.id,
        })
        this.hide()
        // The integration leaves the application's list, so say where it went.
        this.$store.dispatch('toast/success', {
          title: this.$t('promoteIntegration.successTitle'),
          message: this.$t('promoteIntegration.successMessage', {
            name: integration.name,
          }),
        })
      } catch (error) {
        this.handleError(error, 'integration')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
