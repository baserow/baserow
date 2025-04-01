<template>
  <div
    :class="{
      'onboarding-tool-preview': true,
      'onboarding-tool-preview__focus-table': focusOnTable,
    }"
  >
    <div ref="inner" class="onboarding-tool-preview__inner">
      <Highlight ref="highlight"></Highlight>
      <div class="layout">
        <div class="layout__col-1">
          <Sidebar
            ref="sidebar"
            :workspaces="workspaces"
            :selected-workspace="selectedWorkspace"
            :applications="applications"
          ></Sidebar>
        </div>
        <div class="layout__col-2">
          <component
            :is="col2Component"
            v-if="col2Component"
            :data="data"
            :selected-workspace="selectedWorkspace"
            :applications="applications"
            @focusOnTable="handleFocusOnTable"
          ></component>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Sidebar from '@baserow/modules/core/components/sidebar/Sidebar'
import Highlight from '@baserow/modules/core/components/Highlight'
import { populateWorkspace } from '@baserow/modules/core/store/workspace'
import { populateApplication } from '@baserow/modules/core/store/application'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import { WorkspaceOnboardingType } from '@baserow/modules/core/onboardingTypes'
import { clone } from '@baserow/modules/core/utils/object'

export default {
  name: 'AppLayoutPreview',
  components: { Sidebar, Highlight },
  props: {
    data: {
      type: Object,
      required: true,
    },
    highlightDataName: {
      type: String,
      required: false,
      default: '',
    },
  },
  data() {
    return {
      focusOnTable: false,
    }
  },
  computed: {
    selectedWorkspace() {
      const workspace = populateWorkspace({
        id: 0,
        name: this.data[WorkspaceOnboardingType.getType()]?.name || '',
        users: [],
      })
      workspace._.is_onboarding = true
      return workspace
    },
    workspaces() {
      return [this.selectedWorkspace]
    },
    applications() {
      const baseApplication = populateApplication(
        {
          id: 0,
          name: '',
          order: 1,
          type: DatabaseApplicationType.getType(),
          workspace: this.selectedWorkspace,
          tables: [],
        },

        this.$registry
      )
      const application = clone(baseApplication)
      application.name = ''
      const application2 = clone(baseApplication)
      application2.id = -1
      const application3 = clone(baseApplication)
      application3.id = -2
      return [application, application2, application3]
    },
    col2Component() {
      return null
    },
  },
  watch: {
    highlightDataName: {
      immediate: true,
      handler(value) {
        this.updateHighlightedElement(value)
      },
    },
  },
  methods: {
    updateHighlightedElement(value) {
      this.$nextTick(() => {
        if (value) {
          this.$refs.highlight.show(
            `[data-highlight='${this.highlightDataName}']`
          )
        } else {
          this.$refs.highlight.hide()
        }
      })
    },
    handleFocusOnTable(focusOnTable) {
      this.focusOnTable = focusOnTable
    },
  },
}
</script>
