<template>
  <div>
    <Toasts></Toasts>
    <div class="public-view__table">
      <Table
        :database="database"
        :table="table"
        :fields="fields"
        :view="view"
        :read-only="true"
        :table-loading="false"
        :store-prefix="'page/'"
      ></Table>
    </div>
  </div>
</template>

<script>
import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import Table from '@baserow/modules/database/components/table/Table'
import ViewService from '@baserow/modules/database/services/view'
import { PUBLIC_PLACEHOLDER_ENTITY_ID } from '@baserow/modules/database/utils/constants'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import { mapGetters } from 'vuex'
import languageDetection from '@baserow/modules/core/mixins/languageDetection'
import { keyboardShortcutsToPriorityEventBus } from '@baserow/modules/core/utils/events'

export default {
  components: { Table, Toasts },
  mixins: [languageDetection],
  middleware: ['settings'],
  async asyncData({ store, params, error, app, redirect, route }) {
    const slug = params.slug

    // in case the view is password protected, use the token saved in the cookies (if any)
    const publicAuthToken = await store.dispatch(
      'page/view/public/setAuthTokenFromCookiesIfNotSet',
      { slug }
    )

    try {
      await store.dispatch('page/view/public/setIsPublic', true)

      const { data } = await ViewService(app.$client).fetchPublicViewInfo(
        slug,
        publicAuthToken
      )

      const { applications } = await store.dispatch('application/forceSetAll', {
        applications: [
          {
            id: PUBLIC_PLACEHOLDER_ENTITY_ID,
            type: DatabaseApplicationType.getType(),
            tables: [{ id: PUBLIC_PLACEHOLDER_ENTITY_ID }],
            workspace: { id: PUBLIC_PLACEHOLDER_ENTITY_ID },
          },
        ],
      })

      const database = applications[0]
      const table = database.tables[0]
      await store.dispatch('table/forceSelect', { database, table })

      const { fields } = await store.dispatch('field/forceSetFields', {
        fields: data.fields,
      })

      // We must manually set the filters disabled because it should always be false in
      // this case and it's not provided by the backend.
      data.view.filters_disabled = false
      data.view.filter_type = 'AND'
      const { view } = await store.dispatch('view/forceCreate', {
        data: data.view,
      })

      await store.dispatch('view/select', view)

      // It might be possible that the view also has some stores that need to be
      // filled with initial data, so we're going to call the fetch function here.
      const type = app.$registry.get('view', view.type)
      await type.fetch({ store, app }, database, view, fields, 'page/')
      return {
        database,
        table,
      }
    } catch (e) {
      const statusCode = e.response?.status
      // password protected view requires authentication
      if (statusCode === 401) {
        return redirect({
          name: 'database-public-view-auth',
          query: { original: route.path },
        })
      } else if (e.response?.status === 404) {
        return error({ statusCode: 404, message: 'View not found.' })
      } else {
        return error({ statusCode: 500, message: 'Error loading view.' })
      }
    }
  },
  head() {
    const head = { title: this.view.name }
    if (!this.view.show_logo) {
      head.titleTemplate = '%s'
    }
    return head
  },
  computed: {
    ...mapGetters({
      fields: 'field/getAll',
      view: 'view/getSelected',
    }),
  },
  mounted() {
    this.$el.keydownEvent = (event) => this.keyDown(event)
    document.body.addEventListener('keydown', this.$el.keydownEvent)

    if (!this.$config.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS) {
      this.$realtime.connect(true, true)

      const token = this.$store.getters['page/view/public/getAuthToken']
      this.$realtime.subscribe('view', { slug: this.$route.params.slug, token })
    }
  },
  beforeDestroy() {
    document.body.removeEventListener('keydown', this.$el.keydownEvent)

    if (!this.$config.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS) {
      this.$realtime.subscribe(null)
      this.$realtime.disconnect()
    }
  },
  methods: {
    keyDown(event) {
      keyboardShortcutsToPriorityEventBus(event, this.$priorityBus)
    },
  },
}
</script>
