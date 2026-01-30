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
            @focus-on-table="handleFocusOnTable"
          ></component>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import {
  DatabaseOnboardingType,
  DatabaseImportOnboardingType,
  DatabaseScratchTrackOnboardingType,
} from '@baserow/modules/database/onboardingTypes'
import DatabaseTablePreview from '@baserow/modules/database/components/onboarding/DatabaseTablePreview'
import { populateTable } from '@baserow/modules/database/store/table'
import { clone } from '@baserow/modules/core/utils/object'
import Sidebar from '@baserow/modules/core/components/sidebar/Sidebar'
import Highlight from '@baserow/modules/core/components/Highlight'
import { populateWorkspace } from '@baserow/modules/core/store/workspace'
import { populateApplication } from '@baserow/modules/core/store/application'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'

export default {
  name: 'DatabaseAppLayoutPreview',
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
      const name = this.$store.getters['auth/getName']
      const workspace = populateWorkspace({
        id: 0,
        name: this.$t('databaseStep.workspaceName', { name }),
        users: [],
      })
      workspace._.is_onboarding = true
      return workspace
    },
    workspaces() {
      return [this.selectedWorkspace]
    },
    trackTableName() {
      return this.data[DatabaseScratchTrackOnboardingType.getType()]?.tableName
    },
    importTableName() {
      return this.data[DatabaseImportOnboardingType.getType()]?.tableName
    },
    tableName() {
      return this.trackTableName || this.importTableName
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
      application.name = this.data[DatabaseOnboardingType.getType()]?.name || ''
      const application2 = clone(baseApplication)
      application2.id = -1
      const application3 = clone(baseApplication)
      application3.id = -2
      const applications = [application, application2, application3]

      if (this.tableName) {
        applications[0]._.selected = true
        const baseTable = populateTable({
          id: 0,
          name: '',
          order: 0,
          database_id: 0,
        })

        const table = clone(baseTable)
        table._.selected = true
        table.name = this.tableName
        const table2 = clone(baseTable)
        table2.id = -1
        const table3 = clone(baseTable)
        table3.id = -2

        applications[0].tables = [table, table2, table3]
      }

      return applications
    },
    col2Component() {
      return this.trackTableName && this.applications[0].tables.length > 0
        ? DatabaseTablePreview
        : null
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
  mounted() {
    // Add a new selected object to the store, so that it works with the sidebar, but
    // doesn't have influence over the actual selected state of the application.
    const application = { id: this.applications[0].id, _: {} }
    this.$store.commit('application/SET_SELECTED', application)
  },
  methods: {
    updateHighlightedElement(value) {
      this.$nextTick(() => {
        const highlight = this.$refs.highlight
        if (!highlight) {
          return
        }

        if (value) {
          highlight.show(`[data-highlight='${this.highlightDataName}']`)
        } else {
          highlight.hide()
        }
      })
    },
    handleFocusOnTable(focusOnTable) {
      this.focusOnTable = focusOnTable
    },
  },
}
</script>
