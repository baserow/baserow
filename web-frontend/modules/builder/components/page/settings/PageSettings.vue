<template>
  <div>
    <h2 class="box__title">{{ $t('pageSettings.title') }}</h2>
    <Error :error="error"></Error>
    <Alert v-if="success" type="success">
      <template #title>{{ $t('pageSettings.pageUpdatedTitle') }}</template>
      <p>{{ $t('pageSettings.pageUpdatedDescription') }}</p>
    </Alert>
    <PageSettingsForm
      :builder="builder"
      :page="currentPage"
      :default-values="currentPage"
      @submitted="updatePage"
    >
      <div
        v-if="$hasPermission('builder.page.update', currentPage, workspace.id)"
        class="actions actions--right"
      >
        <Button size="large" :loading="loading" :disabled="loading">
          {{ $t('action.save') }}
        </Button>
      </div>
    </PageSettingsForm>
  </div>
</template>

<script>
import error from '@baserow/modules/core/mixins/error'
import PageSettingsForm from '@baserow/modules/builder/components/page/settings/PageSettingsForm'
import { mapActions } from 'vuex'
import { defaultValueForParameterType } from '@baserow/modules/builder/utils/params'

export default {
  name: 'PageSettings',
  components: { PageSettingsForm },
  mixins: [error],
  inject: ['builder', 'currentPage', 'workspace'],
  data() {
    return {
      loading: false,
      success: false,
    }
  },
  methods: {
    ...mapActions({ actionUpdatePage: 'page/update' }),
    async updatePage({
      name,
      path,
      path_params: pathParams,
      query_params: queryParams,
    }) {
      this.success = false
      this.loading = true
      this.hideError()
      try {
        await this.actionUpdatePage({
          builder: this.builder,
          page: this.currentPage,
          values: {
            name,
            path,
            path_params: pathParams,
            query_params: queryParams,
          },
        })
        await Promise.all([
          ...pathParams.map(({ name, type }) =>
            this.$store.dispatch('pageParameter/setParameter', {
              page: this.currentPage,
              name,
              value: defaultValueForParameterType(type),
            })
          ),
          ...queryParams.map(({ name, type }) =>
            this.$store.dispatch('pageParameter/setParameter', {
              page: this.currentPage,
              name,
              value: null,
            })
          ),
        ])
        this.success = true
      } catch (error) {
        this.handleError(error)
      }
      this.loading = false
    },
  },
}
</script>
