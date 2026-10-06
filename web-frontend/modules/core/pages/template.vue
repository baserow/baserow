<template>
  <TemplatePreview v-if="template" :template="template" />
  <div v-else>error</div>
</template>

<script setup>
import TemplatePreview from '@baserow/modules/core/components/template/TemplatePreview'
import TemplateService from '@baserow/modules/core/services/template'

const route = useRoute()
const { $client } = useNuxtApp()

const slug = route.params.slug

const { data: template } = await useAsyncData(`template-${slug}`, async () => {
  try {
    const { data } = await TemplateService($client).fetch(slug)
    return data
  } catch {
    return null
  }
})
</script>
