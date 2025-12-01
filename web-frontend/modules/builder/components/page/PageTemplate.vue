<template>
  <PageTemplateContent
    v-if="!loading && workspace && currentPage && builder"
    :workspace="workspace"
    :builder="builder"
    :current-page="currentPage"
    :mode="mode"
  />
  <PageSkeleton v-else />
</template>

<script>
import { StoreItemLookupError } from '@baserow/modules/core/errors'
import PageTemplateContent from '@baserow/modules/builder/components/page/PageTemplateContent'
import PageSkeleton from '@baserow/modules/builder/components/page/PageSkeleton'
import { DataProviderType } from '@baserow/modules/core/dataProviderTypes'
import { BuilderApplicationType } from '@baserow/modules/builder/applicationTypes'
import { clone } from '@baserow/modules/core/utils/object'

const mode = 'editing'

export default {
  name: 'PageTemplate',
  components: { PageTemplateContent, PageSkeleton },
  props: {
    pageValue: {
      type: Object,
      required: true,
    },
  },
  data() {
    return {
      workspace: null,
      builder: null,
      currentPage: null,
      mode,
      loading: true,
    }
  },
  watch: {
    'pageValue.page.id': {
      handler() {
        this.loadData()
      },
      immediate: true,
    },
  },
  destroyed() {
    // Restore the current application to the selected application if any
    this.$store.dispatch('userSourceUser/setCurrentApplication', {
      application: this.$store.getters['application/getSelected'],
    })
  },
  methods: {
    async loadData() {
      this.loading = true

      try {
        const builderToDisplay = this.pageValue.builder

        if (
          this.$store.getters['userSourceUser/getCurrentApplication']?.id !==
          builderToDisplay.id
        ) {
          // We clone the builder because we are using it in the userSourceUser store
          // And the application is then modified outside of the store elsewhere.
          this.$store.dispatch('userSourceUser/setCurrentApplication', {
            application: clone(builderToDisplay),
          })
        }

        const builder =
          this.$store.getters['userSourceUser/getCurrentApplication']

        const page = this.$store.getters['page/getById'](
          builder,
          this.pageValue.page.id
        )

        const builderApplicationType = this.$registry.get(
          'application',
          BuilderApplicationType.getType()
        )
        await builderApplicationType.loadExtraData(builder)

        await Promise.all([
          this.$store.dispatch('dataSource/fetch', {
            page,
          }),
          this.$store.dispatch('element/fetch', { builder, page }),
          this.$store.dispatch('builderWorkflowAction/fetch', { page }),
        ])

        await DataProviderType.initAll(
          this.$registry.getAll('builderDataProvider'),
          {
            builder,
            page,
            mode,
          }
        )

        this.builder = builder
        this.currentPage = page
        this.workspace = builder.workspace
      } catch (e) {
        // In case of a network error we want to fail hard.
        if (e.response === undefined && !(e instanceof StoreItemLookupError)) {
          throw e
        }
      }

      this.loading = false
    },
  },
}
</script>
