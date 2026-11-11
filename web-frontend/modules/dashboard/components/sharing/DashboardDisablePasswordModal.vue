<template>
  <Modal ref="modal" :small="true">
    <h2 class="box__title">{{ $t('dashboardDisablePasswordModal.title') }}</h2>
    <Error :error="error"></Error>
    <p class="box__description">
      {{ $t('dashboardDisablePasswordModal.description') }}
    </p>
    <div class="actions actions--right actions--gap">
      <Button type="secondary" size="large" :disabled="loading" @click="hide()">
        {{ $t('action.cancel') }}
      </Button>
      <Button
        type="danger"
        size="large"
        :loading="loading"
        :disabled="loading"
        @click="disablePassword()"
      >
        {{ $t('dashboardDisablePasswordModal.disable') }}
      </Button>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import { updateDashboardSharing } from '@baserow/modules/dashboard/utils/sharing'

/**
 * Asks for confirmation before removing the password of a publicly shared
 * dashboard, after which the link works without one again. The `modal` and
 * `error` mixins only exist for the options API, which is why this component
 * doesn't use the composition API.
 */
export default {
  name: 'DashboardDisablePasswordModal',
  mixins: [modal, error],
  props: {
    dashboard: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      loading: false,
    }
  },
  methods: {
    async disablePassword() {
      this.hideError()
      this.loading = true

      try {
        await updateDashboardSharing(this, this.dashboard, {
          public_password: '',
        })
        this.hide()
      } catch (error) {
        this.handleError(error, 'application')
      } finally {
        this.loading = false
      }
    },
  },
}
</script>
