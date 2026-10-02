<template>
  <TemplatePreview v-if="template" :template="template" />
  <div v-else>error</div>
</template>

<script setup>
import { useAsyncData, useNuxtApp, useRoute } from '#imports'
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import TemplateService from '@baserow/modules/core/services/template'

defineOptions({ name: 'Template' })

const route = useRoute()
const { $client } = useNuxtApp()
const { data: template } = await useAsyncData(
  () => `template:${route.params.slug}`,
  async () => {
    try {
      const { data } = await TemplateService($client).fetch(route.params.slug)
      return data
    } catch {
      return null
    }
  }
)
</script>
