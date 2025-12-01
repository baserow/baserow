<template>
  <div>
    <Toasts></Toasts>
    <GuidedTour></GuidedTour>
    <div class="layout">
      <div class="layout__col-1" :style="{ width: col1Width + 'px' }">
        <Sidebar
          :workspaces="workspaces"
          :selected-workspace="selectedWorkspace"
          :applications="applications"
          :collapsed="isCollapsed"
          :width="col1Width"
          :right-sidebar-open="col3Visible"
          @set-col1-width="col1Width = $event"
          @open-workspace-search="openWorkspaceSearch"
        ></Sidebar>
      </div>
      <div
        class="layout__col-2"
        :style="{
          left: col1Width + 'px',
          right: col3Visible ? col3Width + 'px' : 0,
        }"
      >
        <nuxt />
      </div>
      <div
        v-if="col3Visible"
        class="layout__col-3"
        :style="{ width: col3Width + 'px', right: 0 }"
      >
        <RightSidebar :workspace="selectedWorkspace"></RightSidebar>
      </div>
      <HorizontalResize
        class="layout__resize"
        :width="col1Width"
        :style="{ left: col1Width - 2 + 'px' }"
        :min="52"
        :max="300"
        @move="resizeCol1($event)"
      ></HorizontalResize>
      <HorizontalResize
        v-if="col3Visible"
        class="layout__resize"
        :width="col3Width"
        :style="{ right: col3Width - 3 + 'px' }"
        :min="300"
        :max="500"
        :right="true"
        @move="resizeCol3($event)"
      ></HorizontalResize>
      <component
        :is="component"
        v-for="(component, index) in appLayoutComponents"
        :key="index"
      ></component>
    </div>
    <WorkspaceSearchModal ref="workspaceSearchModal"></WorkspaceSearchModal>
  </div>
</template>

<script>
import { mapGetters, mapState } from 'vuex'

import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import Sidebar from '@baserow/modules/core/components/sidebar/Sidebar'
import RightSidebar from '@baserow/modules/core/components/sidebar/RightSidebar'
import undoRedo from '@baserow/modules/core/mixins/undoRedo'
import HorizontalResize from '@baserow/modules/core/components/HorizontalResize'
import GuidedTour from '@baserow/modules/core/components/guidedTour/GuidedTour'
import WorkspaceSearchModal from '@baserow/modules/core/components/workspace/WorkspaceSearchModal.vue'
import { CORE_ACTION_SCOPES } from '@baserow/modules/core/utils/undoRedoConstants'
import {
  isOsSpecificModifierPressed,
  keyboardShortcutsToPriorityEventBus,
} from '@baserow/modules/core/utils/events'

export default {
  components: {
    Toasts,
    Sidebar,
    RightSidebar,
    HorizontalResize,
    GuidedTour,
    WorkspaceSearchModal,
  },
  mixins: [undoRedo],
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'pendingJobs',
  ],
  data() {
    return {
      col1Width: 240,
      col3Width: 400,
      col3Visible: false,
    }
  },
  computed: {
    appLayoutComponents() {
      return Object.values(this.$registry.getAll('plugin'))
        .map((plugin) => plugin.getAppLayoutComponent())
        .filter((component) => component !== null)
    },
    isCollapsed() {
      return this.col1Width < 170
    },
    ...mapState({
      workspaces: (state) => state.workspace.items,
      selectedWorkspace: (state) => state.workspace.selected,
    }),
    ...mapGetters({
      applications: 'application/getAll',
    }),
  },
  created() {
    /*
     The authentication middleware supports loading a refresh token from a query
     param called token. If used we don't want to fill up the users URL bar with a
     massive token, so we want remove it.

     However, crucially, we cannot remove it by issuing a 302 redirect from nuxt
     server as this completely throws away vuex's state, which will
     throw away any authorization obtained by the query param in the auth store.

     Normally this is fine as the client can just reload the token from a cookie,
     however when Baserow is embedded in an iframe on a 3rd party site it cannot
     access these cookies as they are sameSite:lax. So by not issuing a redirect in
     the server to remove the query.token, but instead doing it here, we preserve
     the auth stores state as nuxt will populate it server side and ship it to client.

     This way the client does not need to read the token from the cookies unless they
     refresh the page.
    */
    if (this.$route.query.token) {
      const queryWithoutToken = { ...this.$route.query }
      delete queryWithoutToken.token
      this.$router.replace({ query: queryWithoutToken })
    }
  },
  mounted() {
    // Connect to the web socket so we can start receiving real time updates.
    this.$realtime.connect()
    this.$el.keydownEvent = (event) => this.keyDown(event)
    document.body.addEventListener('keydown', this.$el.keydownEvent)
    this.$store.dispatch(
      'undoRedo/updateCurrentScopeSet',
      CORE_ACTION_SCOPES.root()
    )
    this.$store.dispatch('job/initializePoller')
    this.$bus.$on('toggle-right-sidebar', this.toggleRightSidebar)
  },
  beforeDestroy() {
    this.$realtime.disconnect()
    document.body.removeEventListener('keydown', this.$el.keydownEvent)
    this.$store.dispatch(
      'undoRedo/updateCurrentScopeSet',
      CORE_ACTION_SCOPES.root(false)
    )
    this.$bus.$off('toggle-right-sidebar', this.toggleRightSidebar)
  },
  methods: {
    keyDown(event) {
      // Handle workspace search shortcut (Ctrl/Cmd + K) - only if feature enabled
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        this.openWorkspaceSearch()
        return
      }

      if (
        isOsSpecificModifierPressed(event) &&
        event.key.toLowerCase() === 'z'
      ) {
        // input/textareas/selects/editable dom elements have their own browser
        // controlled undo/redo functionality so don't use our own if they have the
        // focus.
        if (
          !['input', 'textarea', 'select'].includes(
            document.activeElement.tagName.toLowerCase()
          ) &&
          !document.activeElement.isContentEditable
        ) {
          event.shiftKey ? this.redo() : this.undo()
          event.preventDefault()
        }
      }
      keyboardShortcutsToPriorityEventBus(event, this.$priorityBus)
    },

    openWorkspaceSearch() {
      if (this.selectedWorkspace && this.$refs.workspaceSearchModal) {
        this.$refs.workspaceSearchModal.show()
      }
    },
    resizeCol1(event) {
      this.col1Width = event
    },
    resizeCol3(event) {
      this.col3Width = event
    },
    toggleRightSidebar() {
      this.col3Visible = !this.col3Visible
      localStorage.setItem('baserow.rightSidebarOpen', this.col3Visible)
    },
  },
}
</script>
