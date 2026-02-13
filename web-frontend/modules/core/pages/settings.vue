<template>
  <div style="height: 100%; display: flex; flex-direction: column">
    <Tabs
      offset
      full-height
      :route="route"
      large-offset
      @click-disabled="clickDisabled(pages[$event])"
    >
      <Tab
        v-for="page in pages"
        :key="page.type"
        :title="page.name"
        :disabled="!page.navigable"
        :to="page.to"
        :icon="!page.navigable ? 'iconoir-lock' : null"
      >
        <NuxtPage :workspace="workspace" />
      </Tab>
    </Tabs>

    <component
      :is="page.deactivatedModal[0]"
      v-for="page in deactivatedPagesWithModal"
      :key="page.type"
      :ref="(el) => setDeactivatedModalRef(page.type, el)"
      v-bind="page.deactivatedModal[1]"
      :workspace="workspace"
    />
  </div>
</template>

<script setup>
import { useHead } from '#imports'

/* Using Vuex in Nuxt 3 with Composition API */

const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()
const store = nuxtApp.$store
const { $i18n } = nuxtApp

/* asyncData → useAsyncData */
const { data: workspace } = await useAsyncData('workspace', async () => {
  try {
    return await store.dispatch(
      'workspace/selectById',
      parseInt(route.params.workspaceId, 10)
    )
  } catch (e) {
    throw createError({ statusCode: 404, message: 'Workspace not found.' })
  }
})

/* Registry access */
const registry = nuxtApp.$registry

/* Build settings pages */
const workspaceSettingsPageTypes = computed(() =>
  Object.values(registry.getAll('workspaceSettingsPage'))
)

/* Build an array of settings page types they're permitted to view. */
const pages = computed(() => {
  const permittedPages = workspaceSettingsPageTypes.value.filter((instance) =>
    instance.hasPermission(workspace.value)
  )

  return permittedPages.map((instance) => ({
    type: instance.type,
    name: instance.getName(),
    to: instance.getRoute(workspace.value),
    navigable: instance.isFeatureActive(workspace.value),
    deactivatedModal: instance.getFeatureDeactivatedModal(workspace.value),
  }))
})

const deactivatedPagesWithModal = computed(() =>
  pages.value.filter((page) => !page.navigable && page.deactivatedModal)
)

/* Dynamic page title based on current tab */
const currentPageName = computed(() => {
  const currentPage = pages.value.find((p) => p.to?.name === route.name)
  return currentPage?.name || $i18n.t('sidebar.settings')
})

useHead(() => ({
  title: currentPageName.value,
}))

/* Modal refs */
const modalRefs = reactive({})

function setDeactivatedModalRef(type, el) {
  modalRefs[type] = el
}

/* Event bus */
const bus = nuxtApp.$bus

function workspaceDeleted() {
  router.push({ name: 'dashboard' })
}

onMounted(() => {
  bus.$on('workspace-deleted', workspaceDeleted)
})

onBeforeUnmount(() => {
  bus.$off('workspace-deleted', workspaceDeleted)
})

function clickDisabled(page) {
  const ref = modalRefs[page.type]
  if (ref) {
    ref.show()
  }
}
</script>
