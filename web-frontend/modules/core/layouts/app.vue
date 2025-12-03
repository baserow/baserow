<template>
  <div>
    <Toasts />
    <GuidedTour />

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
        />
      </div>

      <div
        class="layout__col-2"
        :style="{
          left: col1Width + 'px',
          right: col3Visible ? col3Width + 'px' : 0,
        }"
      >
        <slot />
      </div>

      <div
        v-if="col3Visible"
        class="layout__col-3"
        :style="{ width: col3Width + 'px', right: 0 }"
      >
        <RightSidebar :workspace="selectedWorkspace" />
      </div>

      <HorizontalResize
        class="layout__resize"
        :width="col1Width"
        :style="{ left: col1Width - 2 + 'px' }"
        :min="52"
        :max="300"
        @move="resizeCol1"
      />

      <HorizontalResize
        v-if="col3Visible"
        class="layout__resize"
        :width="col3Width"
        :style="{ right: col3Width - 3 + 'px' }"
        :min="300"
        :max="500"
        :right="true"
        @move="resizeCol3"
      />

      <component
        :is="component"
        v-for="(component, index) in appLayoutComponents"
        :key="index"
      />
    </div>

    <WorkspaceSearchModal ref="workspaceSearchModal" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'

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

/*definePageMeta({
  middleware: [
    'settings',
    'authenticated',
    'workspacesAndApplications',
    'pendingJobs',
  ],
})*/

const store = useStore()

const col1Width = ref(240)
const col3Width = ref(400)
const col3Visible = ref(false)

const workspaceSearchModal = ref(null)

const workspaces = computed(() => store.state.workspace.items)
const selectedWorkspace = computed(() => store.state.workspace.selected)
const applications = computed(() => store.getters['application/getAll'])

const registry = useNuxtApp().$registry

const appLayoutComponents = computed(() =>
  Object.values(registry.getAll('plugin'))
    .map((plugin) => plugin.getAppLayoutComponent())
    .filter((component) => component)
)

const isCollapsed = computed(() => col1Width.value < 170)

const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()

// Preserve authentication logic
if (route.query.token) {
  const newQuery = { ...route.query }
  delete newQuery.token
  router.replace({ query: newQuery })
}

function openWorkspaceSearch() {
  if (selectedWorkspace.value && workspaceSearchModal.value) {
    workspaceSearchModal.value.show()
  }
}

function resizeCol1(v) {
  col1Width.value = v
}
function resizeCol3(v) {
  col3Width.value = v
}

function toggleRightSidebar() {
  col3Visible.value = !col3Visible.value
  localStorage.setItem('baserow.rightSidebarOpen', col3Visible.value)
}

function keyDown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    openWorkspaceSearch()
    return
  }

  if (isOsSpecificModifierPressed(event) && event.key.toLowerCase() === 'z') {
    const el = document.activeElement
    const avoid =
      ['input', 'textarea', 'select'].includes(el.tagName.toLowerCase()) ||
      el.isContentEditable

    if (!avoid) {
      event.shiftKey ? undoRedo.methods.redo() : undoRedo.methods.undo()
      event.preventDefault()
    }
  }

  keyboardShortcutsToPriorityEventBus(event, nuxtApp.$priorityBus)
}

onMounted(() => {
  nuxtApp.$realtime.connect()

  const handler = (e) => keyDown(e)
  document.body.addEventListener('keydown', handler)
  nuxtApp.$el = { keydownEvent: handler }

  store.dispatch('undoRedo/updateCurrentScopeSet', CORE_ACTION_SCOPES.root())

  store.dispatch('job/initializePoller')

  nuxtApp.$bus.$on('toggle-right-sidebar', toggleRightSidebar)
})

onBeforeUnmount(() => {
  nuxtApp.$realtime.disconnect()

  if (nuxtApp.$el?.keydownEvent) {
    document.body.removeEventListener('keydown', nuxtApp.$el.keydownEvent)
  }

  store.dispatch(
    'undoRedo/updateCurrentScopeSet',
    CORE_ACTION_SCOPES.root(false)
  )

  nuxtApp.$bus.$off('toggle-right-sidebar', toggleRightSidebar)
})
</script>
