<template>
  <div v-if="workspaceExists">
    <div class="dashboard__header" ph-autocapture="dashboard-header">
      <div class="dashboard__header-left">
        <h1
          ref="contextLink"
          class="dashboard__workspace-name"
          @click="
            $refs.context.toggle($refs.contextLink, 'bottom', 'left', -14)
          "
        >
          <div class="dashboard__workspace-name-text">
            <Editable
              ref="rename"
              :value="selectedWorkspace.name"
              @change="renameWorkspace(selectedWorkspace, $event)"
            >
            </Editable>
          </div>
          <i class="dashboard__workspace-name-icon iconoir-nav-arrow-down"></i>
        </h1>
        <component
          :is="component"
          v-for="(component, index) in dashboardWorkspacePlanBadge"
          :key="index"
          :workspace="selectedWorkspace"
          :component-arguments="workspaceComponentArguments"
        ></component>
      </div>
      <WorkspaceContext
        ref="context"
        :workspace="selectedWorkspace"
        @rename="enableRename()"
      ></WorkspaceContext>
      <div class="dashboard__header-right">
        <component
          :is="component"
          v-for="(component, index) in dashboardWorkspaceRowUsageComponent"
          :key="index"
          :workspace="selectedWorkspace"
          :component-arguments="workspaceComponentArguments"
          @workspace-updated="workspaceUpdated($event)"
        ></component>
        <span
          v-if="canCreateCreateApplication"
          ref="createApplicationContextLink"
        >
          <Button
            icon="iconoir-plus"
            tag="a"
            @click="
              $refs.createApplicationContext.toggle(
                $refs.createApplicationContextLink
              )
            "
            >{{ $t('dashboard.addNew') }}</Button
          >
        </span>
      </div>
    </div>
    <div
      class="dashboard__scroll-container"
      ph-autocapture="dashboard-container"
    >
      <div class="dashboard__main">
        <DashboardVerifyEmail
          class="margin-top-0 margin-bottom-0"
        ></DashboardVerifyEmail>
        <WorkspaceInvitation
          v-for="invitation in workspaceInvitations"
          :key="'invitation-' + invitation.id"
          :invitation="invitation"
          class="margin-top-0 margin-bottom-0"
        ></WorkspaceInvitation>
        <div class="dashboard__extras">
          <div
            v-if="canCreateCreateApplication"
            class="dashboard__suggested-templates"
          >
            <h4>{{ $t('dashboard.suggestedTemplates') }}</h4>

            <div class="dashboard__suggested-templates-wrapper">
              <TemplateCard
                v-for="(template, index) in templates"
                :key="index"
                :template="template"
                class="dashboard__suggested-template"
                @click="$refs.templateModal.show(template.slug)"
              ></TemplateCard>

              <TemplateCard
                class="dashboard__suggested-template"
                view-more
                @click="$refs.templateModal.show()"
              >
              </TemplateCard>
            </div>
          </div>
          <div class="dashboard__resources">
            <h4>{{ $t('dashboard.resources') }}</h4>
            <div class="dashboard__resources-wrapper">
              <a
                href="https://baserow.io/user-docs"
                target="_new"
                class="dashboard__resource dashboard__resource--large"
              >
                <div class="dashboard__resource-inner">
                  <span class="dashboard__resource-icon">
                    <i class="iconoir-message-text"></i
                  ></span>

                  <div class="dashboard__resource-content">
                    <h4 class="dashboard__resource-title">
                      {{ $t('dashboard.knowledgeBase') }}
                    </h4>
                    <p class="dashboard__resource-text">
                      {{ $t('dashboard.knowledgeBaseMessage') }}
                    </p>
                  </div>
                </div>
              </a>
              <component
                :is="component"
                v-for="(component, index) in resourceLinksComponents"
                :key="index"
              ></component>
              <a
                href="https://baserow.io/blog/category/tutorials"
                target="_new"
                class="dashboard__resource"
              >
                <div class="dashboard__resource-inner">
                  <span class="dashboard__resource-icon">
                    <i class="iconoir-light-bulb"></i
                  ></span>

                  <div class="dashboard__resource-content">
                    <h4 class="dashboard__resource-title">
                      {{ $t('dashboard.tutorials') }}
                    </h4>
                    <p class="dashboard__resource-text">
                      {{ $t('dashboard.tutorialsMessage') }}
                    </p>
                  </div>
                </div>
              </a>
            </div>
          </div>
        </div>
        <div class="dashboard__wrapper">
          <ul
            v-if="orderedApplicationsInSelectedWorkspace.length"
            class="dashboard__applications"
          >
            <template
              v-for="application in orderedApplicationsInSelectedWorkspace"
            >
              <li
                v-if="getApplicationType(application).isVisible(application)"
                :key="application.id"
              >
                <DashboardApplication
                  :application="application"
                  :workspace="selectedWorkspace"
                  @click="selectApplication(application)"
                />
                <div class="dashboard__application-separator"></div>
              </li>
            </template>
          </ul>
          <div v-else class="dashboard__no-application">
            <img
              src="@baserow/modules/core/assets/images/empty_workspace_illustration.png"
              srcset="
                @baserow/modules/core/assets/images/empty_workspace_illustration@2x.png 2x
              "
            />
            <h4>{{ $t('dashboard.emptyWorkspace') }}</h4>
            <p v-if="canCreateCreateApplication">
              {{ $t('dashboard.emptyWorkspaceMessage') }}
            </p>
            <span
              v-if="canCreateCreateApplication"
              ref="createApplicationContextLink2"
            >
              <Button
                icon="iconoir-plus"
                tag="a"
                @click="
                  $refs.createApplicationContext.toggle(
                    $refs.createApplicationContextLink2
                  )
                "
                >{{ $t('dashboard.addNew') }}</Button
              >
            </span>
          </div>
        </div>
      </div>
      <CreateApplicationContext
        ref="createApplicationContext"
        :workspace="selectedWorkspace"
      >
      </CreateApplicationContext>
    </div>
    <DashboardHelp v-if="dashboardHelpComponents.length === 0"></DashboardHelp>
    <template v-else>
      <component
        :is="component"
        v-for="(component, index) in dashboardHelpComponents"
        :key="index"
      ></component>
    </template>
    <TemplateModal
      ref="templateModal"
      :workspace="selectedWorkspace"
    ></TemplateModal>
  </div>
</template>

<script setup>
import { ref, computed, watchEffect } from 'vue'
import { useRoute, useRouter, useNuxtApp, createError } from '#app'
import { useHead, useAsyncData } from '#imports'

import WorkspaceContext from '@baserow/modules/core/components/workspace/WorkspaceContext'
import CreateApplicationContext from '@baserow/modules/core/components/application/CreateApplicationContext'
import DashboardApplication from '@baserow/modules/core/components/dashboard/DashboardApplication'
import WorkspaceInvitation from '@baserow/modules/core/components/workspace/WorkspaceInvitation'
import TemplateCard from '@baserow/modules/core/components/template/TemplateCard'
import editWorkspace from '@baserow/modules/core/mixins/editWorkspace'
import DashboardVerifyEmail from '@baserow/modules/core/components/dashboard/DashboardVerifyEmail'
import TemplateModal from '@baserow/modules/core/components/template/TemplateModal'
import DashboardHelp from '@baserow/modules/core/components/dashboard/DashboardHelp'

definePageMeta({
  layout: 'app',
  // Note: these middlewares must be explicitly listed because child pages
  // don't automatically inherit parent middleware in Nuxt 3's page meta
  middleware: [
    'settings',
    'authenticated',
    'impersonate',
    'workspacesAndApplications',
  ],
})

defineOptions({
  mixins: [editWorkspace],
})

const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()
const { $store, $registry, $i18n, $hasPermission } = nuxtApp

// ----------------------------------------------------------------------------
// STATE
// ----------------------------------------------------------------------------
const selectedWorkspace = ref(null)
const workspaceComponentArguments = ref({})
const templates = ref([
  {
    name: 'Project Management',
    slug: 'project-management',
    type: 'calendar',
    color: 'yellow',
  },
  {
    name: 'Performance Reviews',
    slug: 'performance-reviews',
    type: 'table',
    color: 'purple',
  },
])

// refs used in template
const context = ref(null)
const contextLink = ref(null)
const createApplicationContext = ref(null)
const createApplicationContextLink = ref(null)
const createApplicationContextLink2 = ref(null)
const rename = ref(null)
const templateModal = ref(null)

async function fetchWorkspaceExtraData(workspace) {
  const plugins = Object.values($registry.getAll('plugin'))
  let mergedData = {
    selectedWorkspace: workspace,
    workspaceComponentArguments: { usageData: [] },
  }

  for (const p of plugins) {
    const workspaceData = await p.fetchAsyncDashboardData(nuxtApp, workspace.id)

    if (workspaceData) {
      mergedData = p.mergeDashboardData(mergedData, workspaceData)
    }
  }

  return mergedData
}

/**
 * Fetch all dashboard-related data for the current workspace.
 * `useAsyncData` now returns the data and we hydrate our refs from it.
 */
const {
  data: dashboardData,
  pending,
  error,
} = await useAsyncData(
  `current-workspace-${route.params.workspaceId}`,
  async () => {
    const workspaceId = parseInt(route.params.workspaceId, 10)

    let workspace
    try {
      workspace = await $store.dispatch('workspace/selectById', workspaceId)
    } catch (e) {
      throw createError({
        statusCode: 404,
        statusMessage: 'Workspace not found.',
      })
    }

    try {
      await $store.dispatch('auth/fetchWorkspaceInvitations')
      return await fetchWorkspaceExtraData(workspace)
    } catch {
      throw createError({
        statusCode: 400,
        statusMessage: 'Error loading dashboard.',
      })
    }
  }
)

/**
 * Hydrate local refs from the async data.
 * Keeps your existing `selectedWorkspace` and `workspaceComponentArguments`
 * reactive and writable for later updates (e.g. `workspaceUpdated`).
 */
watchEffect(() => {
  if (!dashboardData.value) return
  selectedWorkspace.value = dashboardData.value.selectedWorkspace
  workspaceComponentArguments.value =
    dashboardData.value.workspaceComponentArguments
})

useHead(() => ({
  title: $i18n.t('dashboard.title'),
}))

const workspaceInvitations = computed(
  () => $store.getters['auth/getWorkspaceInvitations']
)

const getAllOfWorkspace = (ws) =>
  $store.getters['application/getAllOfWorkspace'](ws)

const dashboardHelpComponents = computed(() =>
  Object.values($registry.getAll('plugin'))
    .reduce(
      (components, plugin) =>
        components.concat(plugin.getDashboardHelpComponents()),
      []
    )
    .filter((c) => c !== null)
)

const dashboardWorkspaceRowUsageComponent = computed(() =>
  Object.values($registry.getAll('plugin'))
    .map((p) => p.getDashboardWorkspaceRowUsageComponent())
    .filter((c) => c !== null)
)

const dashboardWorkspacePlanBadge = computed(() =>
  Object.values($registry.getAll('plugin'))
    .map((p) => p.getDashboardWorkspacePlanBadge())
    .filter((c) => c !== null)
)

const resourceLinksComponents = computed(() =>
  Object.values($registry.getAll('plugin'))
    .map((p) => p.getDashboardResourceLinksComponent())
    .filter((c) => c !== null)
)

const orderedApplicationsInSelectedWorkspace = computed(() =>
  !selectedWorkspace.value
    ? []
    : getAllOfWorkspace(selectedWorkspace.value).sort(
        (a, b) => a.order - b.order
      )
)

const canCreateCreateApplication = computed(() => {
  if (!selectedWorkspace.value) return false
  return $hasPermission(
    'workspace.create_application',
    selectedWorkspace.value,
    selectedWorkspace.value.id
  )
})

/**
 * Check if the workspace exists, because if not, it doesn't make any sense to
 * render anything. This can happen when the workspace is a state where it's
 * deleted, for example.
 */
const workspaceExists = computed(() => {
  if (!selectedWorkspace.value) return false
  return $store.getters['workspace/getAll'].some(
    (w) => w.id === selectedWorkspace.value.id
  )
})

// ----------------------------------------------------------------------------
// METHODS
// ----------------------------------------------------------------------------
function getApplicationType(application) {
  return $registry.get('application', application.type)
}

function selectApplication(application) {
  const type = getApplicationType(application)
  const { $store, $i18n } = nuxtApp
  type.select(application, { $router: router, $store, $i18n })
}

async function workspaceUpdated(workspace) {
  const extraData = await fetchWorkspaceExtraData(workspace)
  workspaceComponentArguments.value = extraData.workspaceComponentArguments
}
</script>
