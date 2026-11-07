<template>
  <div>
    <template v-if="template !== null">
      <div v-if="loading" class="loading-absolute-center"></div>
      <!-- Hidden, not removed, while loading, so that a custom sidebar keeps its
      state, like the chosen workspace, when a new revision is shown. -->
      <div v-show="!loading" class="layout">
        <div class="layout__col-1" :style="{ width: sidebarWidthPx }">
          <slot
            name="sidebar"
            :applications="applications"
            :page="page"
            :select-page="selectPage"
            :select-application="setSelectedApplication"
          >
            <TemplateSidebar
              :template="template"
              :applications="applications"
              :page="page"
              :collapsed="collapsed"
              @selected-page="selectPage"
              @selected-application="setSelectedApplication"
              @collapse-toggled="collapsed = !collapsed"
            ></TemplateSidebar>
          </slot>
        </div>
        <div class="layout__col-2" :style="{ left: sidebarWidthPx }">
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
    // Fixed width of a custom `sidebar` slot. The default sidebar is collapsible.
    sidebarWidth: {
      type: Number,
      required: false,
      default: null,
    },
    // Handles an error loading the content, instead of the default toast.
    loadErrorHandler: {
      type: Function,
      required: false,
      default: null,
    },
  },
  // `loaded` is emitted once the content of the shown revision loaded, or failed.
  emits: ['loaded'],
  data() {
    return {
      loading: false,
      applications: [],
      page: null,
      collapsed: false,
    }
  },
  computed: {
    sidebarWidthPx() {
      if (this.sidebarWidth !== null) {
        return `${this.sidebarWidth}px`
      }
      return this.collapsed ? '48px' : '240px'
    },
    pageComponent() {
      if (this.page !== null) {
        return this.$registry
          .get('application', this.page.application)
          .getTemplatesPageComponent()
      }
      return null
    },
    // The shown content changes with the template or its revision, which is in
    // another workspace, not with a copy of the same template.
    contentKey() {
      return this.template === null
        ? null
        : `${this.template.id}:${this.template.workspace_id}`
    },
  },
  watch: {
    contentKey(value) {
      if (value === null) {
        this.lastRequest++
        this.loading = false
        this.applications = []
        this.page = null
        return
      }
      this.fetchApplications(this.template)
    },
  },
  created() {
    // Only the answer for the shown revision is used, see `fetchApplications`.
    this.lastRequest = 0
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
    /**
     * Loads the applications of the template and selects its first page. A newer
     * revision is loaded in the same preview, so the page of the previous one is
     * never kept, and an older answer that arrives last is ignored.
     */
    async fetchApplications(template) {
      const request = ++this.lastRequest
      this.loading = true

      try {
        const { data } = await ApplicationService(this.$client).fetchAll(
          template.workspace_id
        )
        if (request !== this.lastRequest) {
          return
        }

        this.applications = data.map((application) =>
          populateApplication(application, this.$registry)
        )
        this.page = null

        // A template can optionally have a preferred application that must be opened
        // first in the preview. Try to select that one, and if that's not possible,
        // then try to select the first application of the template.
        const openApplication = this.applications.find(
          (a) => a.id === template.open_application
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
        if (request !== this.lastRequest) {
          return
        }
        this.applications = []
        this.page = null
        if (this.loadErrorHandler) {
          this.loadErrorHandler(error)
        } else {
          notifyIf(error, 'templates')
        }
      } finally {
        if (request === this.lastRequest) {
          this.loading = false
          this.$emit('loaded')
        }
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
    setSelectedApplication(application) {
      this.applications.forEach((app) => {
        app._.selected = application.id === app.id
      })
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
