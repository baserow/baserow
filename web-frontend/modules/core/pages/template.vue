<template>
  <div v-if="data">
    <TemplateDetails
      v-if="selectedTemplate"
      :key="selectedTemplate.id"
      :template="selectedTemplate"
      :categories="selectedTemplateCategories"
      show-back
      class="templates__body"
      @back="selectedTemplate = null"
    />
    <TemplateList
      v-show="!selectedTemplate"
      :categories="data.categories"
      class="templates__body"
      @selected="selectedTemplate = $event"
    />
  </div>
  <div v-else>error</div>
</template>

<script setup>
import { computed, ref } from 'vue'

import TemplateDetails from '@baserow/modules/core/components/template/TemplateDetails'
import TemplateList from '@baserow/modules/core/components/template/TemplateList'
import TemplateService from '@baserow/modules/core/services/template'

// Loads the workspaces of a logged in user, so that they can choose where to
// install the template.
definePageMeta({
  middleware: ['workspacesAndApplications'],
})

const route = useRoute()
const { $client } = useNuxtApp()

const slug = route.params.slug

const { data } = await useAsyncData(`template-${slug}`, async () => {
  try {
    const [{ data: template }, { data: categories }] = await Promise.all([
      TemplateService($client).fetch(slug),
      TemplateService($client).fetchAll(),
    ])
    return { template, categories }
  } catch {
    return null
  }
})

// The linked template is shown first. Going back opens the list of all templates.
const selectedTemplate = ref(data.value?.template ?? null)

const selectedTemplateCategories = computed(() =>
  data.value.categories.filter((category) =>
    category.templates.some((t) => t.id === selectedTemplate.value.id)
  )
)
</script>
