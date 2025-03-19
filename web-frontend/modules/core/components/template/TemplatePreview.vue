<template>
  <div>
    <template v-if="template !== null">
      <div v-if="loading" class="loading-absolute-center"></div>
      <div v-else class="layout">
        <div
          class="layout__col-1"
          :style="{ width: collapsed ? '48px' : '240px' }"
        >
          <TemplateSidebar
            :template="template"
            :applications="applications"
            :page="page"
            :collapsed="collapsed"
            @selected-page="selectPage"
            @collapse-toggled="collapsed = !collapsed"
          ></TemplateSidebar>
        </div>
        <div
          class="layout__col-2"
          :style="{ left: collapsed ? '48px' : '240px' }"
        >
          <component
            :is="pageComponent"
            v-if="page !== null"
            :page-value="page.value"
          ></component>
        </div>
      </div>
    </template>
  </div>
</template>

<script>
import { notifyIf } from '@baserow/modules/core/utils/error'
import ApplicationService from '@baserow/modules/core/services/application'
import { populateApplication } from '@baserow/modules/core/store/application'
import TemplateSidebar from '@baserow/modules/core/components/template/TemplateSidebar'

export default {
  name: 'TemplatePreview',
  components: { TemplateSidebar },
  props: {
    template: {
      required: true,
      validator: (prop) => typeof prop === 'object' || prop === null,
    },
  },
  data() {
    return {
      loading: false,
      applications: [],
      page: null,
      collapsed: false,
    }
  },
  computed: {
    pageComponent() {
      if (this.page !== null) {
        return this.$registry
          .get('application', this.page.application)
          .getTemplatesPageComponent()
      }
      return null
    },
  },
  watch: {
    template(value) {
      if (value === null) {
        this.loading = false
        this.applications = []
        this.page = null
        return
      }
      this.fetchApplications(value)
    },
  },
  created() {
    if (this.template !== null) {
      this.fetchApplications(this.template)
    }
  },
  mounted() {
    this.$nextTick(() => {
      // If the window doesn't have that much space, we want to start with the sidebar
      // collapsed.
      if (window.outerWidth < 640) {
        this.collapsed = true
      }
    })
  },
  methods: {
    async fetchApplications(template) {
      this.loading = true

      try {
        const { data } = await ApplicationService(this.$client).fetchAll(
          template.workspace_id
        )

        this.applications = data.map((application) =>
          populateApplication(application, this.$registry)
        )

        // A template can optionally have a preferred application that must be opened
        // first in the preview. Try to select that one, and if that's not possible,
        // then try to select the first application of the template.
        const openApplication = this.applications.find(
          (a) => a.id === this.template.open_application
        )
        if (openApplication) {
          this.selectApplication(openApplication)
        } else {
          // Check if there is an application that can give us an initial page. The
          // database application type would for example return the first table as page.
          for (let i = 0; i < this.applications.length; i++) {
            const application = this.applications[i]
            if (this.selectApplication(application)) {
              break
            }
          }
        }
      } catch (error) {
        this.applications = []
        notifyIf(error, 'templates')
      } finally {
        this.loading = false
      }
    },
    selectApplication(application) {
      const pageValue = this.$registry
        .get('application', application.type)
        .getTemplatePage(application)
      if (pageValue !== null) {
        application._.selected = true
        this.selectPage({
          application: application.type,
          value: pageValue,
        })
        return true
      }
      return false
    },
    selectPage({ application, value }) {
      this.page = {
        application,
        value,
      }
    },
  },
}
</script>
