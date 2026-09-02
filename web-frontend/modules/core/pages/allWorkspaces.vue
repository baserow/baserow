<template>
  <div class="layout__col-2-scroll layout__col-2-scroll--white-background">
    <div class="all-workspaces">
      <DashboardVerifyEmail
        class="margin-top-0 margin-bottom-2"
      ></DashboardVerifyEmail>
      <WorkspaceInvitation
        v-for="invitation in workspaceInvitations"
        :key="'invitation-' + invitation.id"
        :invitation="invitation"
        class="margin-top-0 margin-bottom-2"
      ></WorkspaceInvitation>

      <AllWorkspacesHeader
        ref="header"
        v-model:search="search"
        v-model:selected-types="selectedTypes"
        v-model:view-mode="viewMode"
        v-model:sort-by="sortBy"
        @collapse-all="collapseAll"
        @expand-all="expandAll"
      ></AllWorkspacesHeader>

      <div v-if="!searchActive" class="all-workspaces__boxes">
        <AllWorkspacesWorkspaceBox
          v-for="workspace in workspaces"
          :key="workspace.id"
          :workspace="workspace"
          :role-name="roleNameOf(workspace)"
          :applications="filteredApplicationsOf(workspace)"
          :total-application-count="applicationsOf(workspace).length"
          :collapsed="collapsedIds.has(workspace.id)"
          :compact="viewMode === 'compact'"
          :sort-by="sortBy"
          @toggle-collapsed="toggleCollapsed(workspace.id)"
          @select-application="selectApplication"
        ></AllWorkspacesWorkspaceBox>
      </div>

      <template v-else>
        <section
          v-if="matchedWorkspaces.length > 0"
          class="all-workspaces__section"
        >
          <h2 class="all-workspaces__section-title">
            {{ $t('allWorkspaces.workspacesSection') }}
          </h2>
          <div class="all-workspaces__boxes">
            <AllWorkspacesWorkspaceBox
              v-for="workspace in matchedWorkspaces"
              :key="'search-workspace-' + workspace.id"
              :workspace="workspace"
              :role-name="roleNameOf(workspace)"
              :applications="[]"
              :total-application-count="applicationsOf(workspace).length"
              :highlight="query"
              header-only
            ></AllWorkspacesWorkspaceBox>
          </div>
        </section>
        <section
          v-if="matchedApplications.length > 0"
          class="all-workspaces__section"
        >
          <h2 class="all-workspaces__section-title">
            {{ $t('allWorkspaces.itemsSection') }}
          </h2>
          <div class="all-workspaces__grid">
            <AllWorkspacesApplicationCard
              v-for="match in matchedApplications"
              :key="'search-application-' + match.application.id"
              :application="match.application"
              :workspace="match.workspace"
              :highlight="query"
              :sort-by="sortBy"
              @click="selectApplication(match.application)"
            ></AllWorkspacesApplicationCard>
          </div>
        </section>
        <div v-if="noResults" class="all-workspaces__empty">
          <div class="all-workspaces__empty-title">
            {{ $t('allWorkspaces.noResultsTitle') }}
          </div>
          <div class="all-workspaces__empty-description">
            {{ $t('allWorkspaces.noResultsDescription', { search: query }) }}
          </div>
          <Button
            class="all-workspaces__empty-action"
            type="secondary"
            tag="a"
            @click="search = ''"
            >{{ $t('allWorkspaces.clearSearch') }}</Button
          >
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { useStore } from 'vuex'
import { useRouter, useNuxtApp } from '#app'
import { useHead } from '#imports'

import DashboardVerifyEmail from '@baserow/modules/core/components/dashboard/DashboardVerifyEmail'
import WorkspaceInvitation from '@baserow/modules/core/components/workspace/WorkspaceInvitation'
import AllWorkspacesHeader from '@baserow/modules/core/components/allWorkspaces/AllWorkspacesHeader'
import AllWorkspacesWorkspaceBox from '@baserow/modules/core/components/allWorkspaces/AllWorkspacesWorkspaceBox'
import AllWorkspacesApplicationCard from '@baserow/modules/core/components/allWorkspaces/AllWorkspacesApplicationCard'
import { CORE_ACTION_SCOPES } from '@baserow/modules/core/utils/undoRedoConstants'
import { getRoleTranslations } from '@baserow/modules/core/store/workspace'
import { matchesQuery } from '@baserow/modules/core/utils/search'
import {
  isTypeFilterActive,
  SORT_BY_CREATED,
  SORT_BY_LAST_VIEWED,
  getApplicationComparator,
  getSearchResultComparator,
  sortWorkspaces,
} from '@baserow/modules/core/utils/allWorkspaces'
import { useUserPreference } from '@baserow/modules/core/composables/useUserPreference'

// Role uids meaning the user only has access through a lower scope. Showing them
// as a badge next to a workspace the user can open would be misleading.
const HIDDEN_ROLE_UIDS = ['NO_ACCESS', 'NO_ROLE_LOW_PRIORITY']

definePageMeta({
  layout: 'app',
  sidebarType: 'all-workspaces',
  middleware: [
    'settings',
    'authenticated',
    'impersonate',
    'workspacesAndApplications',
    'pendingJobs',
  ],
})

const store = useStore()
const router = useRouter()
const { $registry, $i18n } = useNuxtApp()

// The page is workspace agnostic, so the undo/redo buttons in the sidebar footer
// must not act on the scope of a previously visited workspace.
store.dispatch(
  'undoRedo/updateCurrentScopeSet',
  CORE_ACTION_SCOPES.workspace(null)
)

const workspaceInvitations = computed(
  () => store.getters['auth/getWorkspaceInvitations']
)

await store.dispatch('auth/fetchWorkspaceInvitations')

const header = ref(null)

const search = ref('')
const query = computed(() => search.value.trim())
const searchActive = computed(() => query.value !== '')

const applicationTypeCount = $registry.getOrderedList('application').length
// Starting with nothing selected means "no filtering", which makes toggling
// the first type on feel nicer than having to deselect all the others.
const selectedTypes = ref([])
const typeFilterActive = computed(() =>
  isTypeFilterActive(selectedTypes.value, applicationTypeCount)
)

const collapsedIds = ref(new Set())

const viewMode = useUserPreference('all_workspaces_view_mode', 'expanded')
const sortBy = useUserPreference('all_workspaces_sort_by', SORT_BY_LAST_VIEWED)

const roleTranslations = getRoleTranslations($registry)

function roleNameOf(workspace) {
  if (HIDDEN_ROLE_UIDS.includes(workspace.permissions)) {
    return ''
  }
  return roleTranslations[workspace.permissions]?.name ?? ''
}

// Grouped and sorted once per store change instead of once per workspace per
// render. Note that `ApplicationType.isVisible` is deliberately not applied: it
// depends on granular workspace permissions that are only fetched for the
// selected workspace, and no workspace is selected on this page. The backend
// only returns applications the user has access to anyway.
const applicationsByWorkspaceId = computed(() => {
  const grouped = new Map()

  for (const application of store.getters['application/getAll']) {
    const workspaceId = application.workspace.id
    if (!grouped.has(workspaceId)) {
      grouped.set(workspaceId, [])
    }
    grouped.get(workspaceId).push(application)
  }

  const comparator = getApplicationComparator(sortBy.value)
  for (const applications of grouped.values()) {
    applications.sort(comparator)
  }

  return grouped
})

const filteredApplicationsByWorkspaceId = computed(() => {
  if (!typeFilterActive.value) {
    return applicationsByWorkspaceId.value
  }

  const filtered = new Map()
  for (const [workspaceId, applications] of applicationsByWorkspaceId.value) {
    filtered.set(
      workspaceId,
      applications.filter((application) =>
        selectedTypes.value.includes(application.type)
      )
    )
  }
  return filtered
})

function applicationsOf(workspace) {
  return applicationsByWorkspaceId.value.get(workspace.id) ?? []
}

const workspaces = computed(() =>
  sortWorkspaces(
    store.getters['workspace/getAllSorted'],
    sortBy.value,
    applicationsOf
  )
)

function filteredApplicationsOf(workspace) {
  return filteredApplicationsByWorkspaceId.value.get(workspace.id) ?? []
}

const matchedWorkspaces = computed(() =>
  workspaces.value.filter((workspace) =>
    matchesQuery(workspace.name, workspace.id, query.value)
  )
)

const matchedApplications = computed(() => {
  const matches = workspaces.value.flatMap((workspace) =>
    filteredApplicationsOf(workspace)
      .filter((application) =>
        matchesQuery(application.name, application.id, query.value)
      )
      .map((application) => ({ application, workspace }))
  )
  if (sortBy.value !== SORT_BY_CREATED) {
    // Matches come grouped per workspace, but this section is a flat list.
    const comparator = getSearchResultComparator(sortBy.value)
    matches.sort((a, b) => comparator(a.application, b.application))
  }
  return matches
})

const noResults = computed(
  () =>
    matchedWorkspaces.value.length === 0 &&
    matchedApplications.value.length === 0
)

function toggleCollapsed(workspaceId) {
  if (collapsedIds.value.has(workspaceId)) {
    collapsedIds.value.delete(workspaceId)
  } else {
    collapsedIds.value.add(workspaceId)
  }
}

function collapseAll() {
  collapsedIds.value = new Set(workspaces.value.map(({ id }) => id))
}

function expandAll() {
  collapsedIds.value = new Set()
}

async function selectApplication(application) {
  if (application._.loading) {
    return
  }

  const type = $registry.get('application', application.type)
  await store.dispatch('application/setItemLoading', {
    application,
    value: true,
  })
  try {
    await type.select(application, { $router: router, $store: store, $i18n })
  } finally {
    await store.dispatch('application/setItemLoading', {
      application,
      value: false,
    })
  }
}

function keydownCapture(event) {
  if ((event.ctrlKey || event.metaKey) && event.key?.toLowerCase() === 'k') {
    event.preventDefault()
    // Stop the app layout's bubble phase listener from opening the workspace
    // search modal, because on this page the shortcut focuses the inline search.
    event.stopPropagation()
    header.value?.focusSearch()
  }
}

onMounted(() => {
  document.addEventListener('keydown', keydownCapture, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', keydownCapture, true)
})

useHead(() => ({
  title: $i18n.t('allWorkspaces.title'),
}))
</script>
