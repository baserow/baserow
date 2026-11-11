<template>
  <Modal ref="modal">
    <h2 class="box__title">
      {{
        $t('dashboardRotateSlugModal.title', {
          dashboardName: dashboard.name,
        })
      }}
    </h2>
    <Error :error="error"></Error>
    <p>{{ $t('dashboardRotateSlugModal.refreshWarning') }}</p>
    <div class="actions actions--right actions--gap">
      <Button type="secondary" size="large" :disabled="loading" @click="hide()">
        {{ $t('action.cancel') }}
      </Button>
      <Button
        type="primary"
        size="large"
        :loading="loading"
        :disabled="loading"
        @click="rotateSlug()"
      >
        {{ $t('dashboardRotateSlugModal.generateNewUrl') }}
      </Button>
    </div>
  </Modal>
</template>

<script>
import modal from '@baserow/modules/core/mixins/modal'
import error from '@baserow/modules/core/mixins/error'
import DashboardService from '@baserow/modules/dashboard/services/dashboard'

/**
 * Asks for confirmation before replacing the public slug of the dashboard. The
 * `modal` and `error` mixins only exist for the options API, which is why this
 * component doesn't use the composition API.
 */
export default {
  name: 'DashboardRotateSlugModal',
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
    async rotateSlug() {
      this.hideError()
      this.loading = true

      try {
        const { data } = await DashboardService(this.$client).rotateSlug(
          this.dashboard.id
        )
        await this.$store.dispatch('application/forceUpdate', {
          application: this.dashboard,
          data: { slug: data.slug },
        })
        this.$store.dispatch('toast/success', {
          title: this.$t('dashboardRotateSlugModal.success'),
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
