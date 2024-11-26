<template>
  <div>
    <h2 class="box__title">{{ $t('pageVisibilitySettings.title') }}</h2>

    <div>
      <PageVisibilityForm
        :default-values="page"
        @values-changed="updatePageVisibility"
      />
    </div>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import PageVisibilityForm from '@baserow/modules/builder/components/page/settings/PageVisibilityForm'
import { mapActions } from 'vuex'

export default {
  name: 'PageVisibilitySettings',
  components: { PageVisibilityForm },
  mixins: [error],
  inject: ['builder', 'page', 'workspace'],
  data() {
    return {}
  },
  methods: {
    ...mapActions({ actionUpdatePage: 'page/update' }),
    async updatePageVisibility(values) {
      this.hideError()
      try {
        await this.actionUpdatePage({
          builder: this.builder,
          page: this.page,
          values,
        })
      } catch (error) {
        this.handleError(error)
      }
    },
  },
}
</script>
