<template>
  <Context
    ref="context"
    class="sidebar-workspace-picker"
    max-height-if-outside-viewport
    @shown="onShow"
    @hidden="onHidden"
    @keydown.esc="onEscape"
  >
    <SelectSearch
      ref="search"
      v-model="query"
      :aria-label="$t('action.search')"
      @keydown.down.up="onWorkspaceSearchKeydown"
    />
    <ul
      ref="workspaceOptions"
      class="sidebar-workspace-picker__items"
      @keydown="onWorkspaceOptionKeydown"
    >
      <SidebarWorkspacePickerRow
        v-for="workspace in filteredWorkspaces"
        ref="workspaceRows"
        :key="workspace.id"
        :workspace="workspace"
        :selected="workspace.id === selectedWorkspace.id"
        :pending-workspace-id="pendingWorkspaceId"
        :has-unread-notifications="hasUnreadNotifications(workspace.id)"
        @select="selectWorkspace(workspace)"
      />
      <li
        v-if="query && filteredWorkspaces.length === 0"
        class="select__items--empty"
        role="status"
      >
        {{ $t('sidebar.noWorkspacesFound') }}
      </li>
      <li v-if="$hasPermission('create_workspace')">
        <button
          ref="addWorkspace"
          type="button"
          class="sidebar-workspace-picker__add"
          data-workspace-option
          @click="createWorkspaceModal.show()"
        >
          <span
            class="button-icon button-icon--small sidebar-workspace-picker__add-icon"
            aria-hidden="true"
          >
            <i class="button-icon__icon iconoir-plus"></i>
          </span>
          {{ $t('sidebar.addNewWorkspace') }}
        </button>
      </li>
    </ul>
    <CreateWorkspaceModal
      ref="createWorkspaceModal"
      @created="context.hide()"
      @hidden="onCreateWorkspaceHidden"
    ></CreateWorkspaceModal>
  </Context>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import { useStore } from 'vuex'
import { useRoute, useRouter } from '#imports'

import SelectSearch from '@baserow/modules/core/components/SelectSearch.vue'
import SidebarWorkspacePickerRow from '@baserow/modules/core/components/sidebar/SidebarWorkspacePickerRow.vue'
import CreateWorkspaceModal from '@baserow/modules/core/components/workspace/CreateWorkspaceModal.vue'
import { notifyIf } from '@baserow/modules/core/utils/error'
import { escapeRegExp } from '@baserow/modules/core/utils/string'

const props = defineProps({
  workspaces: {
    type: Array,
    required: true,
  },
  selectedWorkspace: {
    type: Object,
    required: true,
  },
})
const emit = defineEmits(['hidden', 'shown'])

const store = useStore()
const route = useRoute()
const router = useRouter()

const context = ref(null)
const search = ref(null)
const workspaceOptions = ref(null)
const workspaceRows = ref([])
const addWorkspace = ref(null)
const createWorkspaceModal = ref(null)
const query = ref('')
const pendingWorkspaceId = ref(null)

const filteredWorkspaces = computed(() => {
  const pattern = new RegExp(escapeRegExp(query.value), 'i')
  return props.workspaces.filter(({ name }) => pattern.test(name))
})

function getWorkspaceOptions() {
  return Array.from(
    workspaceOptions.value.querySelectorAll(
      '[data-workspace-option]:not(:disabled)'
    )
  )
}

function onWorkspaceSearchKeydown(event) {
  if (!event.isComposing) {
    event.preventDefault()
    const index = event.key === 'ArrowDown' ? 0 : -1
    getWorkspaceOptions().at(index)?.focus()
  }
}

function onWorkspaceOptionKeydown(event) {
  if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    return
  }

  const options = getWorkspaceOptions()
  const index = options.indexOf(event.target)
  if (index === -1) {
    return
  }

  const targets = {
    ArrowDown: options[index + 1] ?? search.value,
    ArrowUp: options[index - 1] ?? search.value,
    Home: options[0],
    End: options.at(-1),
  }
  event.preventDefault()
  targets[event.key].focus()
}

function onCreateWorkspaceHidden() {
  if (context.value?.isOpen()) {
    addWorkspace.value?.focus()
  }
}

function onHidden() {
  // The row menus are teleported independently. Hiding only their popovers
  // leaves any dialogs opened from those menus mounted.
  for (const row of workspaceRows.value) {
    row.hideActions()
  }
  emit('hidden')
}

async function onShow() {
  query.value = ''
  emit('shown')
  await nextTick()
  if (context.value?.isOpen()) {
    search.value?.focus()
  }
}

function onEscape(event) {
  if (!event.defaultPrevented) {
    event.preventDefault()
    event.stopPropagation()
    hideAndFocusOpener()
  }
}

function hideAndFocusOpener() {
  const opener = context.value.opener
  context.value.hide()
  opener?.focus()
}

function hasUnreadNotifications(workspaceId) {
  return store.getters['notification/workspaceHasUnread'](workspaceId)
}

async function selectWorkspace(workspace) {
  if (pendingWorkspaceId.value !== null) {
    return
  }
  pendingWorkspaceId.value = workspace.id
  try {
    if (!workspace._.selected) {
      await store.dispatch('workspace/select', workspace)
    }
    const destination = {
      name: 'workspace',
      params: { workspaceId: workspace.id },
    }
    if (route.fullPath !== router.resolve(destination).fullPath) {
      const failure = await router.push(destination)
      if (failure) {
        return
      }
    }
    // Navigating from a global page can replace the entire sidebar.
    if (context.value?.isOpen()) {
      hideAndFocusOpener()
    }
  } catch (error) {
    notifyIf(error, 'workspace')
  } finally {
    pendingWorkspaceId.value = null
  }
}

defineExpose({ toggle: (...args) => context.value.toggle(...args) })
</script>
