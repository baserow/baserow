<template>
  <div class="templates-page">
    <!-- The page doesn't use the app layout, which renders the toasts, like the
    progress and the result of an install. -->
    <Toasts />
    <!-- Keyed by the workspace too, so that the preview shows the content of a
    new revision. -->
    <TemplateDetails
      v-if="selectedTemplate"
      :key="`${selectedTemplate.id}:${selectedTemplate.workspace_id}`"
      :template="selectedTemplate"
      :categories="selectedTemplateCategories"
      show-back
      class="templates__body"
      @back="showList = true"
      @outdated="templateOutdated"
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
    <SharedTemplateList
      v-if="tab === 'shared'"
      v-show="!selectedTemplate"
      :active="!selectedTemplate"
      class="templates__body"
      @selected="selectSharedTemplate"
    >
      <template #head>
        <SegmentControl
          :segments="tabs"
          :active-index="tabIndex"
          type="pills"
          @update:active-index="tab = tabs[$event].value"
        />
      </template>
    </SharedTemplateList>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import SharedTemplateList from '@baserow/modules/core/components/template/SharedTemplateList'
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
// The shared templates opened from the list by slug. They aren't part of the
// official categories.
const sharedTemplates = ref({})

const tab = ref('official')
const tabs = computed(() => [
  {
    value: 'official',
    label: $i18n.t('templateModal.officialTemplates'),
    icon: 'baserow-icon-templates',
  },
  {
    value: 'shared',
    label: $i18n.t('templateModal.sharedTemplates'),
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
  // The linked template is not in the list if the list couldn't be loaded.
  if (currentSlug.value === data.value.template.slug) {
    return data.value.template
  }
  return (
    sharedTemplates.value[currentSlug.value] ??
    data.value.categories
      .flatMap((category) => category.templates)
      .find((t) => t.slug === currentSlug.value) ??
    null
  )
})

watch(
  () => route.params.slug,
  (newSlug) => {
    // Ignores leaving the page, which would show the list until it's unmounted.
    if (route.name === 'template') {
      currentSlug.value = newSlug
      showList.value = false
    }
  }
)

function selectTemplate(template) {
  showList.value = false
  router.push({ name: 'template', params: { slug: template.slug } })
}

function selectSharedTemplate(template) {
  sharedTemplates.value[template.slug] = template
  selectTemplate(template)
}

const selectedTemplateCategories = computed(() => {
  // A user template lists its own categories, which the linked one lacks.
  if (selectedTemplate.value.type === 'user') {
    return selectedTemplate.value.categories ?? []
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
    if (slug === data.value.template.slug) {
      // The data isn't deeply reactive.
      data.value = { ...data.value, template }
    } else {
      // The template's own categories aren't part of the response.
      sharedTemplates.value[slug] = {
        ...sharedTemplates.value[slug],
        ...template,
      }
    }
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
