<template>
  <div class="templates-page">
    <!-- The page doesn't use the app layout, which renders the toasts, like the
    progress and the result of an install. -->
    <Toasts />
    <!-- Keyed by the template only, so that the chosen workspace is kept when a
    new revision is shown. The preview loads its content then. -->
    <TemplateDetails
      v-if="selectedTemplate"
      :key="selectedTemplate.id"
      :template="selectedTemplate"
      :categories="selectedTemplateCategories"
      show-back
      class="templates__body"
      @back="showList = true"
      @outdated="templateOutdated"
      @moderated="publicTemplateList?.refresh()"
    />
    <TemplateList
      v-show="!selectedTemplate && tab === 'official'"
      :categories="data.categories"
      :active="!selectedTemplate && tab === 'official'"
      class="templates__body"
      @selected="selectTemplate"
    >
      <template #head>
        <SegmentControl
          :segments="tabs"
          :active-index="tabIndex"
          type="pills"
          @update:active-index="tab = tabs[$event].value"
        />
      </template>
    </TemplateList>
    <!-- Mounted when its tab is opened, so that it's only loaded when needed. -->
    <PublicTemplateList
      v-if="tab === 'public'"
      v-show="!selectedTemplate"
      ref="publicTemplateList"
      :active="!selectedTemplate"
      class="templates__body"
      @selected="selectPublicTemplate"
    >
      <template #head>
        <SegmentControl
          :segments="tabs"
          :active-index="tabIndex"
          type="pills"
          @update:active-index="tab = tabs[$event].value"
        />
      </template>
    </PublicTemplateList>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import PublicTemplateList from '@baserow/modules/core/components/template/PublicTemplateList'
import TemplateDetails from '@baserow/modules/core/components/template/TemplateDetails'
import TemplateList from '@baserow/modules/core/components/template/TemplateList'
import Toasts from '@baserow/modules/core/components/toasts/Toasts'
import TemplateService from '@baserow/modules/core/services/template'
import { fetchWorkspacesAndApplications } from '@baserow/modules/core/utils/workspace'
import { keyboardShortcutsToPriorityEventBus } from '@baserow/modules/core/utils/events'
import { notifyIf } from '@baserow/modules/core/utils/error'

const route = useRoute()
const router = useRouter()
const nuxtApp = useNuxtApp()
const { $client, $i18n, $store, $priorityBus } = nuxtApp

const slug = route.params.slug

const { data, error } = await useAsyncData(`template-${slug}`, async () => {
  try {
    const [{ data: template }, { data: categories }] = await Promise.all([
      TemplateService($client).fetch(slug),
      // The linked template must still render if the list can't be loaded.
      TemplateService($client)
        .fetchAll()
        .catch(() => ({ data: [] })),
      // The workspaces of a logged in user, so that they can choose where to
      // install the template. Not left to the `workspacesAndApplications`
      // middleware, because it sends a user without workspaces to the onboarding.
      $store.getters['auth/isAuthenticated']
        ? fetchWorkspacesAndApplications(nuxtApp, null)
        : null,
    ])
    return { template, categories }
  } catch (e) {
    if (e.response?.status === 404) {
      throw createError({
        statusCode: 404,
        message: 'Template not found.',
        data: { report: false },
        fatal: true,
      })
    }
    throw e
  }
})

if (error.value) {
  throw error.value
}

// The template in the URL is shown, so that a reload, the browser history or a
// copied link show the same template. Going back opens the list of all templates
// and keeps the URL. The page stays mounted when the slug changes, see the `key`
// of the template page.
const showList = ref(false)
const currentSlug = ref(slug)
const publicTemplates = ref({})
const publicTemplateList = ref(null)
// The id of the public template being opened, so that only the last opened one
// is shown.
let selectingPublic = null

const tab = ref('official')
const tabs = computed(() => [
  {
    value: 'official',
    label: $i18n.t('templateModal.officialTemplates'),
    icon: 'baserow-icon-templates',
  },
  {
    value: 'public',
    label: $i18n.t('templateModal.publicTemplates'),
    icon: 'iconoir-group',
  },
])
const tabIndex = computed(() =>
  tabs.value.findIndex(({ value }) => value === tab.value)
)

const selectedTemplate = computed(() => {
  if (showList.value) {
    return null
  }
  if (publicTemplates.value[currentSlug.value]) {
    return publicTemplates.value[currentSlug.value]
  }
  // The linked template is not in the list if the list couldn't be loaded.
  if (currentSlug.value === data.value.template.slug) {
    return data.value.template
  }
  return (
    data.value.categories
      .flatMap((category) => category.templates)
      .find((t) => t.slug === currentSlug.value) ?? null
  )
})

watch(
  () => route.params.slug,
  (newSlug) => {
    // Ignores leaving the page, which would show the list until it's unmounted.
    if (route.name === 'template') {
      currentSlug.value = newSlug
      showList.value = false
      if (selectedTemplate.value === null) {
        fetchPublicTemplate(newSlug)
      }
    }
  }
)

/**
 * Loads a public template that the page doesn't know, like one opened from the
 * list before a reload, which the browser history goes back to.
 */
async function fetchPublicTemplate(slug) {
  try {
    const { data: template } = await TemplateService($client).fetch(slug)
    publicTemplates.value[slug] = template
  } catch (e) {
    notifyIf(e, 'template')
  }
}

function selectTemplate(template) {
  showList.value = false
  router.push({ name: 'template', params: { slug: template.slug } })
}

/**
 * Shows the public template as it is now, which may have been made private or
 * deleted since the list was loaded. The list is loaded again then.
 */
async function selectPublicTemplate(template) {
  const { id, slug } = template
  selectingPublic = id
  try {
    const { data: fetched } = await TemplateService($client).fetch(slug)
    if (selectingPublic === id && !selectedTemplate.value) {
      publicTemplates.value[slug] = fetched
      selectTemplate(fetched)
    }
  } catch (e) {
    if (e.response?.status === 404) {
      $store.dispatch('toast/error', {
        title: $i18n.t('templateModal.unavailableTitle'),
        message: $i18n.t('templateModal.unavailableDescription'),
      })
      publicTemplateList.value?.refresh()
    } else {
      notifyIf(e, 'template')
    }
  } finally {
    if (selectingPublic === id) {
      selectingPublic = null
    }
  }
}

const selectedTemplateCategories = computed(() => {
  // A user template lists its own categories.
  if (selectedTemplate.value.type === 'user') {
    return selectedTemplate.value.categories
  }
  return data.value.categories.filter((category) =>
    category.templates.some((t) => t.id === selectedTemplate.value.id)
  )
})

/**
 * An install was refused because another revision of the shown user template
 * was made public since it was loaded. The page shows it, so that the user sees
 * what they install. Official templates aren't updated this way.
 */
async function templateOutdated() {
  const { slug } = selectedTemplate.value
  try {
    const { data: template } = await TemplateService($client).fetch(slug)
    publicTemplates.value[slug] = template
  } catch (e) {
    notifyIf(e, 'template')
  }
}

// The page doesn't use the app layout, which turns keyboard shortcuts like the
// search one into priority bus events.
function keyDown(event) {
  keyboardShortcutsToPriorityEventBus(event, $priorityBus)
}

onMounted(() => {
  document.body.addEventListener('keydown', keyDown)
})

onBeforeUnmount(() => {
  document.body.removeEventListener('keydown', keyDown)
})
</script>
